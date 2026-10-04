"""Export the trained Keras model to ONNX, quantize to INT8, calibrate thresholds, write the app files.

  python model/export_onnx.py --data /home/user/data_proc/cafetal --ckpt model/checkpoints/best.keras \
      --ortweb <onnxruntime-web dist dir>

1. tf2onnx (opset 13) -> model/checkpoints/cafetal_fp32.onnx ; max |diff| vs Keras on 20 images.
2. Compressed candidates: static INT8 (onnxruntime QDQ, per-channel, 200 training images for
   calibration), INT8 weights only (DequantizeLinear), fp16 weights only (Cast).
3. Ship the smallest candidate that runs in onnxruntime-web and loses <= --max-f1-drop (default 1
   point) of validation macro-F1 against fp32 (decided on VALIDATION, never on test).
4. Blur threshold (algorithm in model/blur.py): highest value that rejects <= 5 % of the real
   validation images of every coffee class; reports how many heavily blurred copies it catches.
5. Confidence threshold: lowest top-1 threshold in [0.50, 0.90] whose accepted validation
   predictions reach >= 95 % accuracy, both on clean validation images and on clean + phone-like
   degraded copies (so the threshold is not tuned only to clean data).
6. Writes app/model/cafetal.onnx, app/model/labels.json, reports/model_calibration.json.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import onnxruntime as ort  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blur import BLUR_SIZE, laplacian_variance_array  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ORTWEB = os.path.join(REPO, "app", "vendor")
COFFEE = ["sano", "roya", "minador", "phoma", "cercospora", "acaro_rojo"]


def ort_session(path):
    so = ort.SessionOptions()
    so.intra_op_num_threads = 4
    return ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])


def run_onnx(sess, x, batch=64):
    name = sess.get_inputs()[0].name
    return np.concatenate([sess.run(None, {name: x[i:i + batch].astype(np.float32)})[0]
                           for i in range(0, len(x), batch)])


def blur_of_array(arr):
    """Blur score of an already-square uint8 array (same pipeline as the app: resize to 128)."""
    im = Image.fromarray(arr).resize((BLUR_SIZE, BLUR_SIZE), Image.BILINEAR)
    return laplacian_variance_array(np.asarray(im))


def check_ortweb(model_path, dist_dir, x1, size):
    """Run the model in onnxruntime-web (Node, WASM, 1 thread). Returns the parsed JSON or an error dict."""
    if not dist_dir or not os.path.isdir(dist_dir) or not shutil.which("node"):
        return {"ok": False, "error": f"onnxruntime-web dist dir not found ({dist_dir}) or node missing"}
    inp = model_path + ".input.f32"
    x1.astype("<f4").tofile(inp)
    try:
        out = subprocess.run(["node", os.path.join(REPO, "model", "check_ortweb.mjs"), model_path, dist_dir,
                              inp, str(size), "20"], capture_output=True, text=True, timeout=300)
        line = (out.stdout.strip().splitlines() or ["{}"])[-1]
        return json.loads(line) if line.startswith("{") else {"ok": False, "error": out.stderr[-500:]}
    finally:
        os.remove(inp)


def compress_weights(src, dst, mode):
    """Store Conv weights compactly; activations and arithmetic stay float32.

    int8: symmetric per-output-channel int8 + DequantizeLinear (opset 13).
    fp16: float16 + Cast. Both are folded back to float32 when the session loads.
    """
    import onnx
    from onnx import helper, numpy_helper
    m = onnx.load(src)
    inits = {i.name: i for i in m.graph.initializer}
    names = sorted({n.input[1] for n in m.graph.node if n.op_type == "Conv" and n.input[1] in inits})
    new = []
    for name in names:
        w = numpy_helper.to_array(inits[name]).astype(np.float32)
        m.graph.initializer.remove(inits[name])
        if mode == "int8":
            o = w.shape[0]
            mx = np.abs(w.reshape(o, -1)).max(1)
            scale = np.where(mx > 0, mx / 127.0, 1.0).astype(np.float32)
            q = np.clip(np.round(w / scale.reshape(-1, *[1] * (w.ndim - 1))), -127, 127).astype(np.int8)
            m.graph.initializer.extend([numpy_helper.from_array(q, name + "_q"),
                                        numpy_helper.from_array(scale, name + "_scale"),
                                        numpy_helper.from_array(np.zeros(o, np.int8), name + "_zp")])
            new.append(helper.make_node("DequantizeLinear", [name + "_q", name + "_scale", name + "_zp"],
                                        [name], axis=0, name=name + "_dq"))
        else:
            m.graph.initializer.append(numpy_helper.from_array(w.astype(np.float16), name + "_fp16"))
            new.append(helper.make_node("Cast", [name + "_fp16"], [name], to=onnx.TensorProto.FLOAT,
                                        name=name + "_cast"))
    for i, node in enumerate(new):
        m.graph.node.insert(i, node)
    onnx.checker.check_model(m)
    onnx.save(m, dst)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--ckpt", default=os.path.join(REPO, "model", "checkpoints", "best.keras"))
    ap.add_argument("--workdir", default=os.path.join(REPO, "model", "checkpoints"))
    ap.add_argument("--ortweb", default=DEFAULT_ORTWEB, help="onnxruntime-web dist dir (ort.node.min.mjs + .wasm)")
    ap.add_argument("--opset", type=int, default=13)
    ap.add_argument("--calib-images", type=int, default=200)
    ap.add_argument("--target-acc", type=float, default=0.95)
    ap.add_argument("--min-threshold", type=float, default=0.70, help="policy floor for the confidence threshold")
    ap.add_argument("--max-f1-drop", type=float, default=0.01,
                    help="max validation macro-F1 loss vs fp32 accepted for a compressed model")
    ap.add_argument("--force", choices=["int8_static", "int8_weights", "fp16_weights", "fp32"],
                    help="override the automatic choice")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--app-dir", default=os.path.join(REPO, "app", "model"), help="where cafetal.onnx + labels.json go")
    ap.add_argument("--calib-out", default=os.path.join(REPO, "reports", "model_calibration.json"))
    ap.add_argument("--version", default="cafetal-img-v1")
    ap.add_argument("--trained-on", default="JMuBEN/JMuBEN2 (Kenya, Arabica) + PlantDoc and Imagenette as 'otro'; "
                                            "see DATA_CARD.md")
    args = ap.parse_args()
    rng = np.random.default_rng(args.seed)
    meta = json.load(open(os.path.join(args.data, "meta.json")))
    classes, size = meta["classes"], meta["size"]
    os.makedirs(args.workdir, exist_ok=True)
    fp32_path = os.path.join(args.workdir, "cafetal_fp32.onnx")
    va = np.load(os.path.join(args.data, "val.npz"))
    xva, yva = va["x"], va["y"]
    report = {"classes": classes, "size": size}

    # ---- 1. Keras -> ONNX
    import tensorflow as tf
    import tf2onnx
    model = tf.keras.models.load_model(args.ckpt)
    spec = (tf.TensorSpec((None, size, size, 3), tf.float32, name="image"),)
    tf2onnx.convert.from_keras(model, input_signature=spec, opset=args.opset, output_path=fp32_path)
    idx = rng.choice(len(xva), 20, replace=False)
    k_out = model.predict(xva[idx].astype(np.float32), verbose=0)
    s32 = ort_session(fp32_path)
    o_out = run_onnx(s32, xva[idx])
    report["fp32_vs_keras_max_abs_diff"] = float(np.abs(k_out - o_out).max())
    print("fp32 ONNX vs Keras max abs diff:", report["fp32_vs_keras_max_abs_diff"])

    # ---- 2. compressed candidates
    from onnxruntime.quantization import (CalibrationDataReader, CalibrationMethod, QuantFormat,
                                          QuantType, quantize_static)
    from onnxruntime.quantization.shape_inference import quant_pre_process
    tr = np.load(os.path.join(args.data, "train.npz"))
    cal_idx = rng.choice(len(tr["y"]), args.calib_images, replace=False)
    cal_x = tr["x"][np.sort(cal_idx)].astype(np.float32)

    class Reader(CalibrationDataReader):
        def __init__(self):
            self.it = iter(cal_x)

        def get_next(self):
            x = next(self.it, None)
            return None if x is None else {"image": x[None]}

    paths = {"int8_static": os.path.join(args.workdir, "cafetal_int8_static.onnx"),
             "int8_weights": os.path.join(args.workdir, "cafetal_int8_weights.onnx"),
             "fp16_weights": os.path.join(args.workdir, "cafetal_fp16_weights.onnx"),
             "fp32": fp32_path}
    pre_path = os.path.join(args.workdir, "cafetal_fp32_pre.onnx")
    quant_pre_process(fp32_path, pre_path, skip_symbolic_shape=True)
    quantize_static(pre_path, paths["int8_static"], Reader(), quant_format=QuantFormat.QDQ, per_channel=True,
                    activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                    calibrate_method=CalibrationMethod.MinMax)
    compress_weights(fp32_path, paths["int8_weights"], "int8")
    compress_weights(fp32_path, paths["fp16_weights"], "fp16")

    # ---- 3. accuracy (validation) + onnxruntime-web check for each candidate, pick the smallest good one
    p32 = run_onnx(s32, xva)
    f1_32 = f1_score(yva, p32.argmax(1), average="macro")
    x1 = xva[idx[:1]].astype(np.float32)
    cands, preds, sessions = {}, {}, {}
    for name, path in paths.items():
        sess = s32 if name == "fp32" else ort_session(path)
        p = p32 if name == "fp32" else run_onnx(sess, xva)
        web = check_ortweb(path, args.ortweb, x1, size)
        if web.get("ok"):
            web["max_abs_diff_vs_python_ort"] = float(np.abs(np.array(web.pop("probs")) -
                                                             sess.run(None, {"image": x1})[0][0]).max())
        f1 = f1_score(yva, p.argmax(1), average="macro")
        cands[name] = {"size_bytes": os.path.getsize(path), "val_macro_f1": round(float(f1), 4),
                       "val_accuracy": round(float((p.argmax(1) == yva).mean()), 4),
                       "top1_agreement_with_fp32": round(float((p.argmax(1) == p32.argmax(1)).mean()), 4),
                       "ortweb_node": web}
        preds[name], sessions[name] = p, sess
        print(name, {k: v for k, v in cands[name].items() if k != "ortweb_node"},
              "ortweb ok" if web.get("ok") else f"ortweb FAILED {web.get('error')}", flush=True)
    report["candidates"] = cands
    report["fp32_vs_keras_max_abs_diff"] = report.pop("fp32_vs_keras_max_abs_diff")
    good = [n for n in ("int8_static", "int8_weights", "fp16_weights", "fp32")
            if cands[n]["ortweb_node"].get("ok") and f1_32 - cands[n]["val_macro_f1"] <= args.max_f1_drop]
    if not (args.force or good):
        sys.exit("no candidate ran in onnxruntime-web: check --ortweb (see the ortweb_node errors above)")
    choice = args.force or good[0]
    report["shipped"] = choice
    report["choice_reason"] = (f"forced {args.force}" if args.force else
                               f"smallest candidate that runs in onnxruntime-web (WASM) and loses <= "
                               f"{100 * args.max_f1_drop:.1f} points of validation macro-F1 vs fp32")
    report["val_macro_f1"] = {"fp32": round(float(f1_32), 4), "shipped": cands[choice]["val_macro_f1"]}
    report["val_accuracy"] = {"fp32": cands["fp32"]["val_accuracy"], "shipped": cands[choice]["val_accuracy"]}
    report["ortweb_node_check"] = {"fp32": cands["fp32"]["ortweb_node"], choice: cands[choice]["ortweb_node"]}
    ship_path, pv, s8 = paths[choice], preds[choice], sessions[choice]
    print("shipping", choice, "-", report["choice_reason"])

    # ---- 4. blur threshold on validation (real images vs heavily blurred copies)
    full = va["view"] == "full"
    real = va["blur"]
    blurred = {}
    for radius in (3, 4):
        blurred[radius] = np.array([blur_of_array(np.asarray(Image.fromarray(a).filter(
            ImageFilter.GaussianBlur(radius)))) for a in xva])
    per_class_p5 = {}
    for k, c in enumerate(classes):
        m = full & (yva == k)
        if m.any() and c in COFFEE:
            per_class_p5[c] = float(np.percentile(real[m], 5))
    blur_thr = float(np.floor(min(per_class_p5.values()) * 10) / 10)
    stats = {}
    for k, c in enumerate(classes):
        m = full & (yva == k)
        if not m.any():
            continue
        stats[c] = {"n": int(m.sum()), "real_median": round(float(np.median(real[m])), 1),
                    "real_p5": round(float(np.percentile(real[m], 5)), 1),
                    "real_rejected": round(float((real[m] < blur_thr).mean()), 4),
                    "blur_r3_median": round(float(np.median(blurred[3][m])), 1),
                    "blur_r3_rejected": round(float((blurred[3][m] < blur_thr).mean()), 4),
                    "blur_r4_rejected": round(float((blurred[4][m] < blur_thr).mean()), 4)}
    report["blur_threshold"] = {"value": blur_thr, "rule": "floor(min over coffee classes of the 5th percentile "
                                                           "of real validation images), 1 decimal",
                                "per_class": stats}
    print("blur threshold", blur_thr, json.dumps(stats, indent=1))

    # ---- 5. confidence threshold on validation: clean AND phone-like degraded copies
    from evaluate import DEGRADATIONS
    sship = s8
    blur_va = np.where(np.isnan(real), np.array([blur_of_array(a) for a in xva]), real)
    sets = {"clean": (pv, blur_va)}
    for name in ("jpeg_q25", "gaussian_blur_r2", "brightness_x0.6", "brightness_x1.4", "downscale_64"):
        xd = np.stack([DEGRADATIONS[name](a) for a in xva]).astype(np.uint8)
        sets[name] = (run_onnx(sship, xd), np.array([blur_of_array(a) for a in xd]))
    yy = np.concatenate([yva] * len(sets))
    pp = np.concatenate([v[0] for v in sets.values()])
    bb = np.concatenate([v[1] for v in sets.values()])

    def curve_for(probs, blurv, y):
        top1, pred = probs.max(1), probs.argmax(1)
        rows = []
        for t in np.round(np.arange(0.50, 0.901, 0.01), 2):
            m = (top1 >= t) & (blurv >= blur_thr)
            acc = float((pred[m] == y[m]).mean()) if m.any() else float("nan")
            rows.append({"threshold": float(t), "coverage": round(float(m.mean()), 4),
                         "selective_accuracy": round(acc, 4)})
        return rows

    curve_clean = curve_for(pv, blur_va, yva)
    curve_all = curve_for(pp, bb, yy)
    ok = [t for t, c, d in zip(np.round(np.arange(0.50, 0.901, 0.01), 2), curve_clean, curve_all)
          if c["selective_accuracy"] >= args.target_acc and d["selective_accuracy"] >= args.target_acc]
    data_thr = float(ok[0]) if ok else 0.90
    thr = max(data_thr, args.min_threshold)
    report["threshold"] = {
        "value": thr, "data_driven_value": data_thr, "policy_floor": args.min_threshold,
        "floor_reason": "validation images come from the same Kenyan dataset as training, so confidence on "
                        "real field photos will be lower and less reliable; the floor keeps the PLAN.md "
                        "default 0.70 when the data-driven value is lower",
        "rule": f"lowest t in [0.50,0.90] where accepted validation predictions reach >= {args.target_acc:.0%} "
                f"accuracy on clean images AND on clean + 5 phone-like degradations (jpeg q25, blur r2, "
                f"brightness x0.6/x1.4, downscale 64); blur-rejected images count as not accepted"
                + ("" if ok else " (not reached -> 0.90)"),
        "curve": curve_clean, "curve_with_degradations": curve_all}
    print("threshold", thr, next(c for c in curve_clean if c["threshold"] == thr),
          next(c for c in curve_all if c["threshold"] == thr))

    # ---- 6. write app files
    app_dir = args.app_dir
    os.makedirs(app_dir, exist_ok=True)
    dst = os.path.join(app_dir, "cafetal.onnx")
    shutil.copyfile(ship_path, dst)
    sess = ort_session(dst)
    labels = {
        "version": args.version,
        "classes": classes,
        "input": {"name": sess.get_inputs()[0].name, "size": size, "layout": "NHWC", "dtype": "float32",
                  "range": "0-255 RGB, no normalisation (preprocessing is inside the model)"},
        "output": {"name": sess.get_outputs()[0].name, "type": "probabilities"},
        "threshold": thr,
        "blur_threshold": blur_thr,
        "file": "cafetal.onnx",
        "size_bytes": os.path.getsize(dst),
        "trained_on": args.trained_on,
    }
    with open(os.path.join(app_dir, "labels.json"), "w") as fh:
        json.dump(labels, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.makedirs(os.path.dirname(args.calib_out), exist_ok=True)
    with open(args.calib_out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(json.dumps(labels, indent=2))


if __name__ == "__main__":
    main()
