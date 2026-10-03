"""Train the Cafetal leaf classifier (MobileNetV3-Small, ImageNet weights) on the prepared arrays.

Stage 1: frozen backbone, train the head.  Stage 2: unfreeze the top blocks (BatchNorm stays
frozen) with a low, cosine-decayed learning rate. A checkpoint is written after every epoch and
the script resumes from it, so it can run in chunks (--max-minutes) or in the background.

  python model/train.py --data /home/user/data_proc/cafetal --out model/checkpoints
  python model/train.py ... --max-minutes 9      # stop before an epoch would pass 9 minutes; rerun to resume

Final model: <out>/best.keras (best validation macro-F1 over all epochs).
"""
import argparse
import csv
import json
import math
import os
import time

import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
import tensorflow as tf  # noqa: E402
from sklearn.metrics import f1_score  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_model(size, n_classes, dropout=0.3):
    base = tf.keras.applications.MobileNetV3Small(
        input_shape=(size, size, 3), include_top=False, weights="imagenet",
        include_preprocessing=True)  # preprocessing (0-255 -> -1..1) lives inside the model
    inp = tf.keras.Input((size, size, 3), name="image")
    x = base(inp, training=False)  # BatchNorm always in inference mode
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(dropout)(x)
    out = tf.keras.layers.Dense(n_classes, activation="softmax", name="probs")(x)
    return tf.keras.Model(inp, out, name="cafetal"), base


def set_trainable(base, stage, unfreeze_from):
    if stage == 1:
        base.trainable = False
        return
    base.trainable = True
    names = [layer.name for layer in base.layers]
    cut = names.index(unfreeze_from)
    for i, layer in enumerate(base.layers):
        layer.trainable = i >= cut and not isinstance(layer, tf.keras.layers.BatchNormalization)


# ---------------------------------------------------------------- augmentation (all classes)
def gaussian_blur(x, sigma):
    r = 4
    t = tf.range(-r, r + 1, dtype=tf.float32)
    k = tf.exp(-(t ** 2) / (2.0 * sigma ** 2))
    k = k / tf.reduce_sum(k)
    kx = tf.tile(tf.reshape(k, [1, 2 * r + 1, 1, 1]), [1, 1, 3, 1])
    ky = tf.tile(tf.reshape(k, [2 * r + 1, 1, 1, 1]), [1, 1, 3, 1])
    y = tf.pad(x[None], [[0, 0], [r, r], [r, r], [0, 0]], mode="REFLECT")
    y = tf.nn.depthwise_conv2d(y, kx, [1, 1, 1, 1], "VALID")
    y = tf.nn.depthwise_conv2d(y, ky, [1, 1, 1, 1], "VALID")
    return y[0]


def maybe(p, fn, x):
    return tf.cond(tf.random.uniform([]) < p, lambda: fn(x), lambda: x)


def augment(img, size):
    """uint8 HxWx3 -> float32 0-255. Strong photometric augmentation so haze/colour is not a shortcut."""
    x = tf.image.convert_image_dtype(img, tf.float32)
    x = tf.image.random_flip_left_right(x)
    x = tf.image.random_flip_up_down(x)
    x = tf.image.rot90(x, tf.random.uniform([], 0, 4, tf.int32))
    # random crop/zoom (side 55-100 %), slight aspect change
    s = tf.random.uniform([], 0.55, 1.0)
    ar = tf.random.uniform([], 0.85, 1.18)
    h = tf.cast(tf.minimum(1.0, s * tf.sqrt(ar)) * size, tf.int32)
    w = tf.cast(tf.minimum(1.0, s / tf.sqrt(ar)) * size, tf.int32)
    x = tf.image.random_crop(x, tf.stack([h, w, 3]))
    x = tf.image.resize(x, [size, size])
    # photometric
    x = maybe(0.8, lambda v: v * tf.random.uniform([], 0.6, 1.4), x)                       # brightness
    x = maybe(0.8, lambda v: tf.image.adjust_contrast(v, tf.random.uniform([], 0.6, 1.4)), x)
    x = maybe(0.6, lambda v: tf.image.adjust_saturation(tf.clip_by_value(v, 0, 1),
                                                        tf.random.uniform([], 0.5, 1.5)), x)
    x = maybe(0.4, lambda v: tf.image.adjust_hue(tf.clip_by_value(v, 0, 1),
                                                 tf.random.uniform([], -0.04, 0.04)), x)
    x = tf.clip_by_value(x, 0.0, 1.0)

    def haze(v):  # washed-out / foggy look, like many rust crops
        a = tf.random.uniform([], 0.1, 0.5)
        c = tf.random.uniform([1, 1, 3], 0.6, 1.0)
        return v * (1 - a) + a * c

    def autocontrast(v):  # the opposite: stretch to full range
        lo = tf.reduce_min(v, axis=[0, 1], keepdims=True)
        hi = tf.reduce_max(v, axis=[0, 1], keepdims=True)
        return (v - lo) / tf.maximum(hi - lo, 1e-3)

    x = maybe(0.3, haze, x)
    x = maybe(0.25, autocontrast, x)
    x = maybe(0.25, lambda v: gaussian_blur(v, tf.random.uniform([], 0.5, 2.5)), x)

    def down_up(v):
        d = tf.random.uniform([], 48, 129, tf.int32)
        return tf.image.resize(tf.image.resize(v, [d, d]), [size, size])

    x = maybe(0.2, down_up, x)
    x = tf.clip_by_value(x, 0.0, 1.0)
    x = maybe(0.4, lambda v: tf.image.adjust_jpeg_quality(v, tf.random.uniform([], 20, 91, tf.int32)), x)
    x = maybe(0.2, lambda v: v + tf.random.normal(tf.shape(v), 0.0, tf.random.uniform([], 0.005, 0.04)), x)
    x = tf.clip_by_value(x, 0.0, 1.0)
    x = tf.reshape(x, [size, size, 3])
    return x * 255.0


def make_train_ds(x, y, size, batch, seed):
    n = len(y)

    def gen():
        rng = np.random.default_rng(seed)
        for i in rng.permutation(n):
            yield x[i], y[i]

    ds = tf.data.Dataset.from_generator(
        gen, output_signature=(tf.TensorSpec((size, size, 3), tf.uint8), tf.TensorSpec((), tf.int64)))
    ds = ds.map(lambda a, b: (augment(a, size), b), num_parallel_calls=tf.data.AUTOTUNE)
    return ds.batch(batch).prefetch(2)


def predict(model, x, batch=64):
    out = []
    for i in range(0, len(x), batch):
        out.append(model(x[i:i + batch].astype(np.float32), training=False).numpy())
    return np.concatenate(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default=os.path.join(REPO, "model", "checkpoints"))
    ap.add_argument("--stage1-epochs", type=int, default=4)
    ap.add_argument("--stage2-epochs", type=int, default=8)
    ap.add_argument("--lr1", type=float, default=1e-3)
    ap.add_argument("--lr2", type=float, default=2e-4)
    ap.add_argument("--unfreeze-from", default="expanded_conv_6_expand")
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--max-minutes", type=float, default=0, help="0 = no limit")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    tf.keras.utils.set_random_seed(args.seed)
    t_start = time.time()

    meta = json.load(open(os.path.join(args.data, "meta.json")))
    classes, size = meta["classes"], meta["size"]
    tr = np.load(os.path.join(args.data, "train.npz"))
    va = np.load(os.path.join(args.data, "val.npz"))
    xtr, ytr = tr["x"], tr["y"]
    xva, yva = va["x"], va["y"]
    counts = np.bincount(ytr, minlength=len(classes))
    class_weight = {i: float(len(ytr) / (len(classes) * max(c, 1))) for i, c in enumerate(counts)}
    print("train counts", dict(zip(classes, counts.tolist())), "val", len(yva), "class_weight", class_weight)

    state_path = os.path.join(args.out, "state.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else \
        {"stage": 1, "epoch": 0, "best_f1": -1.0, "epoch_seconds": None}
    model, base = build_model(size, len(classes))
    if os.path.exists(os.path.join(args.out, "last.weights.h5")):
        model.load_weights(os.path.join(args.out, "last.weights.h5"))
        print("resumed", state)
    log_path = os.path.join(REPO, "reports", "model_training_log.csv")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    new_log = not os.path.exists(log_path) or state["stage"] == 1 and state["epoch"] == 0

    while state["stage"] <= 2:
        stage, n_ep = state["stage"], (args.stage1_epochs if state["stage"] == 1 else args.stage2_epochs)
        if state["epoch"] >= n_ep:
            state.update(stage=stage + 1, epoch=0)
            continue
        if args.max_minutes and state["epoch_seconds"]:
            if (time.time() - t_start + state["epoch_seconds"] * (2.0 if stage == 2 else 1.0)) / 60 > args.max_minutes:
                print("time budget reached; rerun to resume", state)
                break
        set_trainable(base, stage, args.unfreeze_from)
        e = state["epoch"]
        lr = args.lr1 if stage == 1 else args.lr2 * 0.5 * (1 + math.cos(math.pi * e / n_ep))
        model.compile(optimizer=tf.keras.optimizers.Adam(lr), loss="sparse_categorical_crossentropy",
                      metrics=["accuracy"])
        t0 = time.time()
        hist = model.fit(make_train_ds(xtr, ytr, size, args.batch, args.seed + 100 * stage + e),
                         epochs=1, class_weight=class_weight, verbose=2)
        pva = predict(model, xva)
        f1 = f1_score(yva, pva.argmax(1), average="macro")
        acc = float((pva.argmax(1) == yva).mean())
        secs = time.time() - t0
        print(f"stage {stage} epoch {e + 1}/{n_ep} lr {lr:.2e} loss {hist.history['loss'][-1]:.4f} "
              f"val_acc {acc:.4f} val_macroF1 {f1:.4f} ({secs:.0f}s)", flush=True)
        model.save_weights(os.path.join(args.out, "last.weights.h5"))
        if f1 > state["best_f1"]:
            state["best_f1"] = float(f1)
            state["best"] = {"stage": stage, "epoch": e + 1}
            model.save(os.path.join(args.out, "best.keras"))
        with open(log_path, "w" if new_log else "a", newline="") as fh:
            w = csv.writer(fh)
            if new_log:
                w.writerow(["stage", "epoch", "lr", "train_loss", "train_acc", "val_acc", "val_macro_f1", "seconds"])
                new_log = False
            w.writerow([stage, e + 1, f"{lr:.2e}", f"{hist.history['loss'][-1]:.4f}",
                        f"{hist.history['accuracy'][-1]:.4f}", f"{acc:.4f}", f"{f1:.4f}", f"{secs:.0f}"])
        state.update(epoch=e + 1, epoch_seconds=secs)
        json.dump(state, open(state_path, "w"), indent=2)
    if state["stage"] > 2:
        state["done"] = True
        json.dump(state, open(state_path, "w"), indent=2)
        print("training done; best", state.get("best"), "val macro-F1", state["best_f1"])


if __name__ == "__main__":
    main()
