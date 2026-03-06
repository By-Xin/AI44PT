# Nature 10 Human vs AI Reading Report

## Inputs
- Human gold: `/Users/xinby/Downloads/Nature 10_coding.xlsx`
- AI raw bundle reviewed: `/Users/xinby/Desktop/AI44pt/AI44PT_Desktop/results/raw_responses/raw_batch_20251203_191752/raw_responses_20251203_191752.json`

## Core Finding
- The AI bundle does not correspond to the same 10 Nature articles. Title alignment is 0/10, so direct evaluation is not methodologically valid.

## Title Alignment Check
| ID | Human title (short) | AI title (short) | Title match |
|---:|---|---|---|
| 1 | Feasibility of peak temperature targets in / light of institutional constraints | Understanding voluntary program performance: Introducing the diffusion network perspective | False |
| 4 | Elevated urban energy risks due to / climate-driven biophysical feedbacks | Assessing the institutionalization of private sustainability governance in a changing coff | False |
| 5 | Global patterns and drivers of tropical / aboveground carbon changes | Business interests in salmon aquaculture certification: Competition or collective action? | False |
| 9 | Relaxing fertility policies and / delaying retirement age increase / China’s carbon emissi | Transparency in transnational governance: The determinants of information disclosure of vo | False |
| 18 | Energy and socioeconomic system / transformation through a decade of / IPCC-assessed scena | Can the hidden hand of the market be an effective and legitimate regulator? The case of an | False |
| 19 | Representing gender inequality in scenarios / improves understanding of climate / challeng | Institutional design of ecolabels: Sponsorship signals rule strength | False |
| 27 | High-income groups disproportionately / contribute to climate extremes worldwide | The Transformation of organic regulation: The ambiguous effects of publicization | False |
| 30 | Improving cost–benefit analyses for / health-considered climate mitigation / policymaking | Punishing environmental crimes: An empirical study from lower courts to the court of appea | False |
| 40 | Restoration cannot be scaled up globally to save reefs from loss and degradation | Orchestrating sustainability: The case of European Union biofuel governance | False |
| 50 | Power price stability and the insurance value of renewable technologies | When soft regulation is not enough: The integrated pollution prevention and control direct | False |

## Human Gold Labels (Q15)
- ID 1: `Type 4` -> normalized `Type 4`
- ID 4: `Type 1` -> normalized `Type 1`
- ID 5: `Type 4` -> normalized `Type 4`
- ID 9: `Type 1` -> normalized `Type 1`
- ID 18: `Type 1` -> normalized `Type 1`
- ID 19: `Type 4` -> normalized `Type 4`
- ID 27: `Type 4` -> normalized `Type 4`
- ID 30: `Type 2` -> normalized `Type 2`
- ID 40: `Type 4` -> normalized `Type 4`
- ID 50: `Type 2` -> normalized `Type 2`

## AI Q16 Snapshot From Reviewed Bundle
- ID 1: runs=4, success=4, Q16 majority=`Type 1`, votes=`Type 1:2; Type 2:2`
- ID 4: runs=4, success=4, Q16 majority=`Type 2`, votes=`Type 2:3; Type 3:1`
- ID 5: runs=4, success=4, Q16 majority=`Type 1`, votes=`Type 1:4`
- ID 9: runs=4, success=4, Q16 majority=`Type 3`, votes=`Type 3:2; Type 2:2`
- ID 18: runs=4, success=4, Q16 majority=`Type 3`, votes=`Type 3:4`
- ID 19: runs=4, success=4, Q16 majority=`Type 1`, votes=`Type 1:3; Type 2:1`
- ID 27: runs=4, success=4, Q16 majority=`Type 3`, votes=`Type 3:4`
- ID 30: runs=4, success=4, Q16 majority=`Type 2`, votes=`Type 4:1; Type 2:3`
- ID 40: runs=4, success=4, Q16 majority=`Type 3`, votes=`Type 3:2; Type 2:2`
- ID 50: runs=4, success=4, Q16 majority=`Type 3`, votes=`Type 3:2; Type 2:2`

## Diagnostic Only: Forced ID-Based Match (Invalid)
- If titles are ignored and IDs are force-matched, match rate is 1/10 = 0.1.
- This number must not be used as model performance because the document set is mismatched.

## Conclusion
- Existing AI outputs in this workspace are from another corpus (same numeric IDs but different paper titles).
- A valid human-vs-AI report for Nature 10 requires running AI on these exact 10 papers and then comparing Q15/Q16 on matched titles.