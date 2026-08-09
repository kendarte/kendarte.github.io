# Placeholder content — delete before merging

This branch intentionally contains invented metrics, development durations and debugging examples so the final portfolio structure can be reviewed with realistic content.

**None of the items marked with `data-placeholder` should be treated as a factual claim. Do not merge this branch until every item is replaced or removed.**

No testimonial, employer, client, award or shipped-title claim has been invented.

## Fast audit

Run this search from the repository root:

```bash
rg -n 'data-placeholder' --glob '*.html'
```

The result must be empty before the final merge. After replacing the content, remove each `data-placeholder` attribute and delete this file.

## Homepage placeholders

| Marker | Invented content | Replace with |
| --- | --- | --- |
| `taek-defect-reduction` | 37 recurring defects reduced to 4 | A measured before/after result, or a qualitative result if no count exists |
| `horse-operator-time` | 5 hours reduced to 18 minutes | Real manual and automated production time |
| `euclid-slice-duration` | 12-minute chapter | Actual continuous-play duration |
| `euclid-blockers` | 14 blockers reduced to 2 | Real issue count, test result or non-numeric outcome |
| `contact-response-time` | Reply within one business day | A response promise you can consistently keep |

## Taek-Won-Cop placeholders

| Marker | Invented content | Information needed |
| --- | --- | --- |
| `taek-development-time` | 14 months, part-time | Start/end dates and approximate workload |
| `taek-defects-before` / `taek-defects-after` | 37 reproduced / 4 remaining | Real bug log counts or a qualitative replacement |
| `taek-bug-target-snap` | Target behind cover | Symptom, reliable reproduction steps, root cause and final fix |
| `taek-bug-camera` | Wrong camera restored | A real camera/state transition failure |
| `taek-bug-input` | Permanent defense lock | A real input or cleanup failure |
| `taek-bug-animation` | Duplicate hit windows | A real animation/combat timing failure |

## Horse Racer placeholders

| Marker | Invented content | Information needed |
| --- | --- | --- |
| `horse-development-time` | 9 weeks, part-time | Start/end dates and approximate workload |
| `horse-operator-time` | 5 hours reduced to 18 minutes | Actual before/after production time |
| `horse-recording-test` | 100/100 correct filenames | Real batch size and success/failure result |
| `horse-bug-finish-drift` | Cross-machine finish drift | A real timing or movement defect |
| `horse-bug-camera` | Shot oscillation | A real camera-director defect |
| `horse-bug-filename` | Wrong race ID in exports | A real recorder or batch defect |
| `horse-bug-deadheat` | Duplicate winner event | A real outcome-resolution defect |

## Euclid Wars placeholders

| Marker | Invented content | Information needed |
| --- | --- | --- |
| `euclid-development-time` | 11 weeks, part-time | Start/end dates and approximate workload |
| `euclid-slice-duration` | 12 minutes | Actual continuous-play duration |
| `euclid-blockers-before` / `euclid-blockers-after` | 14 blockers / 2 remaining | Real test or issue results |
| `euclid-bug-cursor` | Cursor not restored | A real dialogue/input defect |
| `euclid-bug-objective` | Duplicate objective update | A real progression defect |
| `euclid-bug-door` | Door state reset | A real persistence or environment defect |
| `euclid-bug-control` | Movement during opening shot | A real control hand-off defect |

## Information to collect for the factual version

Send the following in rough notes; polished writing is not required:

1. Rank the roles you would accept: gameplay programmer, Unity developer, tools programmer, technical artist, technical generalist, contract work, full-time work.
2. For each project: dates, team size, your exact role, approximate hours, engine version and target platform.
3. For each project: three real bugs using `symptom → cause → fix → verified result`.
4. Any measured result: time saved, configurations generated, defects fixed, test runs, frame rate, load time, build size or iteration time.
5. What you personally built, what came from an asset/package and what another person built.
6. Whether a downloadable build, private code review or live interview demo is possible.
7. Work availability: contract/full-time/part-time, start date, preferred overlap hours and relocation limits.
8. Any factual outside proof: shipped work, course taught, student/project count, client permission, recommendation or public contribution.

If a number was never measured, do not estimate it after the fact. Replace it with a concrete qualitative outcome such as “the interrupted path now restores control through one shared cleanup routine.”
