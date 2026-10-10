#!/bin/bash
# Rebuild every derived artefact from results/analysis.json and stage the site. Fails if any placeholder survives.
set -e
cd "$(dirname "$0")"
python3 experiments/analyze.py > /dev/null
python3 paper/iclr/gen_tables.py > /dev/null
python3 paper/iclr/gen_appendix_assets.py > /dev/null
python3 figures/build_figures.py > /dev/null
python3 figures/build_teaser.py > /dev/null
python3 figures/build_gifs.py > /dev/null
(cd paper/iclr && tectonic paper_iclr_submission.tex > /dev/null 2>&1 && tectonic paper_iclr_preprint.tex > /dev/null 2>&1)
cp paper/iclr/paper_iclr_submission.pdf paper/iclr/paper_iclr_preprint.pdf docs/
python3 docs/gen_site.py > /dev/null
if grep -rl "PLACEHOLDER\|LADDER-\|D4-VERDICT\|D4-EVIDENCE\|SPEND-README\|FILM-NOTE" paper/iclr/paper_body.tex paper/iclr/paper_appendix.tex docs/index.html README.md video/script.md; then
  echo "placeholders remain"; exit 1
fi
echo "published: docs/index.html, docs/*.pdf, docs/assets/*"
