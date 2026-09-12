## Description
<!-- Provide a clear summary of the changes made and the problem being solved -->

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Refactor / Code cleanliness (improving architecture or readability)
- [ ] Documentation update

## Pipeline Stages Affected
- [ ] Stage 1: Frames & Keyframe Selection
- [ ] Stage 2: Dynamic Object Masking (YOLO)
- [ ] Stage 3: Structure-from-Motion (COLMAP)
- [ ] Stage 3b: Georeferencing & Scale
- [ ] Stage 5: Dense Reconstruction (OpenMVS)
- [ ] Stage 6: Surface & Terrain Meshing (OpenMVS / 2.5D TIN)
- [ ] Stage 7: Export (GLB, LAZ, DSM, Orthomosaic)
- [ ] Web Studio / API Server
- [ ] Non-pipeline / Utility / CI

## Verification
- [ ] All unit tests pass (`python -m pytest -v`)
- [ ] No large binaries, cache files, or raw video committed
- [ ] GLB materials validated (doubleSided=true, metallicFactor=0.0)
