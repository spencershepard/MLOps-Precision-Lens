## Anomalib Installation
Recommended installation method is via requirements.txt file.  However, if starting fresh, Anomalib installation is as follows:

```bash
pip install anomalib[optional_dependencies]
anomalib install
```

Optional dependencies include hardware acceleration libraries and models. https://github.com/open-edge-platform/anomalib?tab=readme-ov-file#-installation

Documentation: https://anomalib.readthedocs.io/en/v2.1.0/markdown/get_started/anomalib.html

### Troubleshooting
SentencePiece dependency is not compatible with Python 3.13.  Use Python 3.12 or lower.