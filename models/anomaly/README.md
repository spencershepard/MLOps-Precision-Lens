## Anomalib Installation
Recommended installation method is via requirements.txt file.  However, anomalib installation can be a bit tricky, and you may want to customize this for your hardware. 

Example installing everything with requirements.txt, and then customizing the installation:
```bash
pip install -r requirements.txt
pip uninstall anomalib
pip uninstall torch
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cu128
pip install anomalib[full]
```

Optional dependencies include hardware acceleration libraries and models. https://github.com/open-edge-platform/anomalib?tab=readme-ov-file#-installation

Documentation: https://anomalib.readthedocs.io/en/v2.1.0/markdown/get_started/anomalib.html

### Troubleshooting
SentencePiece dependency is not compatible with Python 3.13.  Use Python 3.12 or lower.