#!/bin/sh
# Vercel build for the phone app: copy app/ and content/ (they must stay side by side) into public/.
# Vercel runs this from the project's Root Directory, which must be the repository root.
set -e
echo "Cafetal build in $(pwd):"
ls
if [ ! -d app ] || [ ! -d content ]; then
  echo "ERROR: app/ and content/ are not in this folder. In Vercel, open Settings > Build and Deployment" >&2
  echo "and leave Root Directory empty (the repository root), with no Build Command or Output Directory override." >&2
  exit 1
fi
rm -rf public
mkdir public
cp -R app content public/
echo "Copied $(find public -type f | wc -l) files into public/"
