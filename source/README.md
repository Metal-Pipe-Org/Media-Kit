# Rebuilding the icons

Every image in this repository is rendered by the scripts in this folder, so a colour, angle or size can
be changed and all files rebuilt at once.

## Scripts

1. [`pipe_render.py`](pipe_render.py) renders the 3D steel pipe: lighting, surface texture, rust, the cut
   edge and the dark inside.
2. [`build.py`](build.py) sets the colours and the pipe's position for MetalPipeOrg and writes every file
   in the repository root and in `variants/metalpipeorg/`.

## Running

From the repository root:

```sh
python3 -m venv .venv
.venv/bin/pip install -r source/requirements.txt
.venv/bin/python source/build.py
```

The build overwrites the existing files in place. Check the result with `git diff --stat` before
committing.
