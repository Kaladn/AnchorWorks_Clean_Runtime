# AnchorWorks College-Grad Corpus Curation

Goal: feed AnchorWorks enough clean language fields that counts can form stable clouds without teaching the renderer to guess.

Core path:

```text
approved source
-> plain text / normalized Q&A rows
-> lexicon recognition
-> symbol streams
-> 6-1-6 counts
-> local overlays / global AWSC
-> top-K answer assembly
```

## Hard Laws

```text
No bulk download before approval.
No account-gated scraping.
No license-unknown ingestion.
No unanswered worksheets unless answers are supplied.
No Q/A row enters counts until answer text is resolved.
```

## External Work Root

All curation planning artifacts are written outside the repo:

```text
D:\AnchorWorks_Data_Curation\college_grad_core
```

Generate the pack:

```powershell
python D:\AnchorWorks_Clean_Runtime\Anchorworks\tools\build_data_curation_pack.py
```

Outputs:

```text
ACTION_LINKS.md
HF_QA_DATASETS.md
source_manifest.json
qa_conversion_contract.json
```

## First Q/A Dataset Candidates

Use small, shaped Q/A before web-scale material:

| Dataset | Why |
|---|---|
| [allenai/sciq](https://huggingface.co/datasets/allenai/sciq) | Clean science question, answer, support rows. |
| [allenai/openbookqa](https://huggingface.co/datasets/allenai/openbookqa) | Compact open-book science Q/A. |
| [rajpurkar/squad](https://huggingface.co/datasets/rajpurkar/squad) | Context-grounded question/answer rows. |
| [cais/mmlu](https://huggingface.co/datasets/cais/mmlu) | Broad college subjects; use selected configs only. |
| [openai/gsm8k](https://huggingface.co/datasets/openai/gsm8k) | Arithmetic word-problem language and answer shape. |
| [openai/openai_humaneval](https://huggingface.co/datasets/openai/openai_humaneval) | Tiny programming probe for CS lane. |

## First Pull Recommendation

```text
1. SciQ
2. OpenBookQA
3. SQuAD
4. MMLU selected STEM + college computer science
5. GSM8K
6. HumanEval as tiny CS probe
```

## User Approval Checklist

```text
[ ] Pick allowed source domains.
[ ] Review dataset/page licenses.
[ ] Set row caps per dataset.
[ ] Choose Q/A conversion policy.
[ ] Choose first CS-major lane.
[ ] Approve ingestion order.
```

Tiny law:

```text
Feed counts clean fields first. Scale only after the clouds behave.
```
