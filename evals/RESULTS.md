# Evaluation results

## Sentiment (expected effect on the stock)

| Dataset | Model | N | Accuracy | Macro-F1 | F1 pos / neg / neu | Pos↔Neg flips |
|---|---|---:|---:|---:|---|---:|
| built-in | vader-plain | 110 | 56.4% | 0.565 | 0.55 / 0.61 / 0.53 | 13 |
| built-in | vader | 110 | 78.2% | 0.782 | 0.78 / 0.77 / 0.79 | 10 |

*Pos↔Neg flips* = headlines scored in the opposite direction — the expensive mistake.

## Catalyst tagger (built-in set)

Micro precision **0.98** · recall **0.91** · F1 **0.95**

| Tag | TP | FP | FN |
|---|---:|---:|---:|
| block_deal | 2 | 0 | 0 |
| capex | 1 | 0 | 0 |
| corporate_action | 3 | 0 | 0 |
| ipo | 2 | 0 | 0 |
| lock_in | 1 | 0 | 0 |
| m_and_a | 3 | 0 | 0 |
| management | 2 | 0 | 0 |
| order_win | 5 | 0 | 0 |
| pledge | 1 | 0 | 0 |
| rating_down | 2 | 0 | 0 |
| rating_up | 5 | 0 | 0 |
| regulatory | 7 | 0 | 0 |
| results | 9 | 1 | 4 |

### Misclassified by `vader-plain` (first 15)

- gold **positive**, got *neutral*: Orion Cables bags Rs 640 crore transmission order from state utility
- gold **positive**, got *neutral*: Brokerage upgrades Lumen Retail to buy, sees 30% upside
- gold **positive**, got *neutral*: Sable Foods hits record high as volumes beat estimates
- gold **positive**, got *neutral*: Nimbus Power commissions 300 MW solar plant ahead of schedule
- gold **positive**, got *negative*: Pioneer Pharma gets USFDA approval for generic cancer drug
- gold **positive**, got *neutral*: Zenith Steel posts record quarterly revenue
- gold **positive**, got *neutral*: Broker initiates Meridian Tech with outperform rating
- gold **positive**, got *neutral*: Ivory Cement reports 25% jump in EBITDA per tonne
- gold **positive**, got *neutral*: Summit Realty pre-sales climb 40% year on year
- gold **positive**, got *negative*: Willow Finance loss narrows sharply as provisions fall
- gold **positive**, got *neutral*: Beacon Telecom adds 3 million subscribers, beats estimates
- gold **positive**, got *negative*: Polar Appliances upgraded to overweight by global brokerage
- gold **positive**, got *negative*: Ember Energy cuts net debt by half, shares rise
- gold **positive**, got *neutral*: Orchid Hotels revenue per room hits all-time high
- gold **positive**, got *neutral*: Sterling Capital Goods order book swells to Rs 18,000 crore

### Misclassified by `vader` (first 15)

- gold **positive**, got *neutral*: Orion Cables bags Rs 640 crore transmission order from state utility
- gold **positive**, got *neutral*: Nimbus Power commissions 300 MW solar plant ahead of schedule
- gold **positive**, got *negative*: Pioneer Pharma gets USFDA approval for generic cancer drug
- gold **positive**, got *neutral*: Zenith Steel posts record quarterly revenue
- gold **positive**, got *neutral*: Summit Realty pre-sales climb 40% year on year
- gold **positive**, got *negative*: Willow Finance loss narrows sharply as provisions fall
- gold **positive**, got *negative*: Ember Energy cuts net debt by half, shares rise
- gold **positive**, got *neutral*: Sterling Capital Goods order book swells to Rs 18,000 crore
- gold **positive**, got *negative*: Cypress Pharma shares jump after settling patent dispute
- gold **positive**, got *negative*: Opal Infra emerges lowest bidder for Rs 900 crore highway project
- gold **negative**, got *positive*: Vantage Chemicals Q3 profit falls 30% as margins shrink
- gold **negative**, got *neutral*: Nimbus Power promoter pledges additional 8% stake
- gold **negative**, got *neutral*: Income tax department raids Granite Infra offices
- gold **negative**, got *positive*: Crest Bank gross NPAs rise sharply, provisions jump
- gold **negative**, got *neutral*: Falcon Aviation grounds 12 aircraft due to engine issues

### Catalyst mismatches

- expected ['results'], got —: Crest Bank net interest income rises 18%, asset quality improves
- expected ['results'], got —: Willow Finance loss narrows sharply as provisions fall
- expected ['results'], got —: Ridge Auto turns profitable for the first time in six quarters
- expected —, got ['results']: Orchid Hotels revenue per room hits all-time high
- expected ['results'], got —: Saffron Agro stock steady after mixed quarter
