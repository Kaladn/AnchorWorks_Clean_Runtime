# AW Inference Kernel TODO

Goal: make the missing admission layer real as an external callable package, then wire AnchorWorks through it without allowing raw top-K word salad to escape.

Core law:

```text
Search finds.
Counts weigh.
Inference admits.
Renderer speaks.
```

Boundary:

```text
The kernel does not own truth.
The kernel does not mutate lexicons.
The kernel does not write counts.
The kernel does not generate facts.
The kernel only decides whether candidate answer paths are lawful.
```

## Finish Line

- [x] External package exists at `src/aw_inference_kernel`.
- [x] `AnchorWorks.inference` remains as a import facade only.
- [x] Kernel output always includes `fact_authority: false`.
- [x] Kernel output always includes trace steps for frame creation and candidate admission/rejection.
- [x] Renderer cannot fall back to raw top-K speech when the kernel rejects all candidates.
- [x] First proof questions are covered by tests:
  - `why worry about laws of physics?`
  - `what is inertia?`
  - `who is isaac newton?`
  - missing-anchor variants such as `who is issac newton`
- [x] Tests pass from `D:\AnchorWorks_Clean_Runtime\test\test data\tests`.

## Implementation Steps

1. [x] Add external package contracts and engine.
2. [x] Move activity/frame/candidate/rule/answer-plan behavior into the external package.
3. [x] Leave `AnchorWorks.inference` importing from the external package.
4. [x] Add the no-raw-fallback renderer guard.
5. [x] Add tests for external import, output contract, all-rejected candidates, and ClearSpeak speech guard.
6. [x] Run focused inference tests.
7. [x] Run full unittest suite.

## Non-Goals

- No UI changes.
- No V2 work.
- No count writes.
- No lexicon mutation.
- No document ingestion.
- No neural training.

