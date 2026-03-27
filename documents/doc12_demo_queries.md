# Demo Query Reference Guide

## Purpose
This document lists the exact queries designed to demonstrate vector RAG failure 
and GraphRAG success. Each answer requires traversing multiple documents. 
No single document contains the complete answer.

---

## Demo Query 1 — The Safe Prescription (3-hop)

**Query:**
"Patient PT-001 has Type 2 Diabetes and Hypertension and is currently taking 
Metformin and Lisinopril. Their doctor wants to prescribe Fluconazole for oral 
thrush. Is this safe?"

**Why vector fails:**
- Chunks about Metformin do not mention Fluconazole interactions
- Chunks about Fluconazole mention CYP2C9 and CYP3A4 interactions
- No single chunk says "Fluconazole is safe with Metformin and Lisinopril"
- Vector retrieves drug facts and patient facts separately; cannot assemble safety verdict

**Required graph traversal:**
1. PT-001 -[PRESCRIBED]-> Metformin
2. PT-001 -[PRESCRIBED]-> Lisinopril
3. Fluconazole -[INHIBITS]-> CYP2C9
4. Metformin -[CLEARED_BY]-> OCT2/MATE (NOT CYP2C9)
5. Lisinopril -[NOT_METABOLIZED_BY]-> CYP enzymes
6. Fluconazole -[INHIBITS_MODERATELY]-> CYP3A4
7. Atorvastatin -[METABOLIZED_BY]-> CYP3A4
8. PT-001 -[PRESCRIBED]-> Atorvastatin 40mg (moderate dose, single low fluconazole dose unlikely significant)

**Correct graph answer:** SAFE. Fluconazole 150mg single dose has no clinically significant 
interaction with Metformin (different clearance pathway) or Lisinopril (no hepatic metabolism). 
Monitor for mild atorvastatin accumulation but single dose fluconazole is low risk.

**Contrast with PT-005:** Same diabetes + fluconazole scenario but PT-005 takes Glipizide 
(sulfonylurea, CYP2C9 substrate) making it DANGEROUS — demonstrated in CASE-003.

---

## Demo Query 2 — The Dangerous Prescription (4-hop)

**Query:**
"Patient PT-004 has Heart Failure and Atrial Fibrillation and is on Digoxin, 
Spironolactone, Warfarin, and Lisinopril. They develop a serious fungal infection. 
Why is prescribing Fluconazole dangerous for this patient, and what should be used instead?"

**Why vector fails:**
- Chunks about Fluconazole mention CYP2C9 and CYP3A4
- Chunks about Warfarin mention CYP2C9 metabolism
- Chunks about Digoxin mention P-glycoprotein
- Chunks about Spironolactone mention potassium retention
- No single chunk connects: Fluconazole → CYP2C9 → Warfarin → bleeding AND Fluconazole → QT → arrhythmia risk in AF patient simultaneously

**Required graph traversal:**
1. PT-004 -[HAS_CONDITION]-> Atrial Fibrillation
2. PT-004 -[HAS_CONDITION]-> Heart Failure
3. PT-004 -[PRESCRIBED]-> Warfarin
4. PT-004 -[PRESCRIBED]-> Digoxin
5. PT-004 -[PRESCRIBED]-> Spironolactone
6. PT-004 -[PRESCRIBED]-> Lisinopril
7. Fluconazole -[INHIBITS]-> CYP2C9
8. Warfarin -[METABOLIZED_BY]-> CYP2C9 → Warfarin levels rise → bleeding risk
9. Fluconazole -[CAUSES]-> QT_Prolongation
10. Atrial_Fibrillation -[INCREASES_RISK_OF]-> QT_Related_Arrhythmia
11. Spironolactone + Lisinopril -[COMBINED_RISK]-> Hyperkalemia
12. Heart_Failure -[REQUIRES]-> Spironolactone + ACE_Inhibitor combination
13. Lisinopril -[IS_A]-> ACE_Inhibitor
14. Alternative -[SAFE_FOR]-> Post-Transplant → Anidulafungin, Caspofungin, Micafungin (no CYP interactions)

**Correct graph answer:** DANGEROUS for three simultaneous reasons:
1. Warfarin-Fluconazole: CYP2C9 inhibition raises INR to dangerous levels
2. QT prolongation risk: Fluconazole + underlying AF = arrhythmia risk
3. Alternative available: Echinocandin antifungals (Anidulafungin, Caspofungin) have no CYP interactions; prescribe these instead

---

## Demo Query 3 — The Transplant Triple Danger (5-hop)

**Query:**
"Patient PT-003 is a kidney transplant patient on Tacrolimus. A covering physician 
wants to prescribe Fluconazole. Why is the transplant pharmacist right to intervene, 
and what is the complete chain of harm?"

**Why vector fails:**
- Chunks about transplant mention immunosuppression generally
- Chunks about Tacrolimus mention CYP3A4
- Chunks about Fluconazole mention CYP3A4 inhibition
- No chunk connects: covering physician → no transplant protocol knowledge → prescribes fluconazole → CYP3A4 inhibition → tacrolimus accumulates → nephrotoxicity → loses transplanted kidney

**Required graph traversal:**
1. PT-003 -[HAS_CONDITION]-> Kidney_Transplant
2. PT-003 -[PRESCRIBED]-> Tacrolimus
3. Tacrolimus -[METABOLIZED_BY]-> CYP3A4
4. Fluconazole -[INHIBITS]-> CYP3A4
5. CYP3A4_inhibition -[CAUSES]-> Tacrolimus_accumulation
6. Tacrolimus_accumulation -[CAUSES]-> Nephrotoxicity
7. Nephrotoxicity -[THREATENS]-> Transplanted_Kidney
8. HOSP-002 -[HAS_PROTOCOL]-> TRANSPLANT-001
9. TRANSPLANT-001 -[REQUIRES]-> Pharmacist_Review_Before_Dispensing_Antifungal
10. PHARM-001 (Rebecca Torres) -[INTERCEPTED]-> Prescription
11. Alternative: Caspofungin -[NOT_METABOLIZED_BY]-> CYP3A4 → Safe alternative

**Correct graph answer:** Five-hop danger chain. Fluconazole inhibits CYP3A4 → Tacrolimus cannot be metabolized → Tacrolimus blood level doubles or triples → nephrotoxicity destroys transplanted kidney. Pharmacist correctly substituted Caspofungin (echinocandin) which has no CYP3A4 interaction.

---

## Demo Query 4 — Multi-Drug Cascade (6-hop)

**Query:**
"Patient PT-008 is on Amiodarone, Warfarin, and Digoxin. If Fluconazole is added 
for a fungal infection, trace every interaction that occurs."

**Why vector fails:**
- This requires modeling a three-way drug cascade
- Binary drug interaction checkers and vector search both evaluate drug pairs, not combinations
- No single document describes the Fluconazole → Amiodarone → Digoxin cascade as a chain

**Required graph traversal:**
1. PT-008 -[PRESCRIBED]-> Amiodarone
2. PT-008 -[PRESCRIBED]-> Warfarin  
3. PT-008 -[PRESCRIBED]-> Digoxin
4. Fluconazole -[INHIBITS]-> CYP2C9
5. CYP2C9 -[METABOLIZES]-> Warfarin → Warfarin rises → INR rises → bleeding risk
6. Fluconazole -[INHIBITS_MODERATELY]-> CYP3A4
7. CYP3A4 -[METABOLIZES]-> Amiodarone → Amiodarone rises
8. Amiodarone -[INHIBITS]-> P-glycoprotein
9. P-glycoprotein -[CLEARS]-> Digoxin → Digoxin rises → Digoxin toxicity
10. Fluconazole -[PROLONGS]-> QT_interval
11. Amiodarone -[PROLONGS]-> QT_interval
12. QT_additive_prolongation -[CAUSES]-> Torsades_de_pointes
13. PT-008 -[HAS_CONDITION]-> Atrial_Fibrillation → additional arrhythmia risk
14. CASE-004 -[DOCUMENTS]-> This_exact_cascade_occurring_in_real_patient

**Correct graph answer:** Three simultaneous cascades:
- Cascade A: Fluconazole → ↑Warfarin → bleeding  
- Cascade B: Fluconazole → ↑Amiodarone → Amiodarone inhibits P-gp → ↑Digoxin → digoxin toxicity
- Cascade C: Fluconazole + Amiodarone → additive QT prolongation → torsades de pointes → cardiac arrest risk
This is documented as CASE-004 in the clinical cases registry.

---

## Demo Query 5 — Supply Chain to Patient Safety (4-hop)

**Query:**
"If Teva Pharmaceuticals has a manufacturing shutdown at their fluconazole facility, 
which patients in the registry are directly affected and what are the clinical consequences?"

**Why vector fails:**
- Chunks about Teva mention manufacturing and generics
- Chunks about patients mention their medications
- No chunk links Teva → fluconazole supply → specific patients currently prescribed fluconazole → clinical consequence of antifungal shortage

**Required graph traversal:**
1. Teva -[MANUFACTURES]-> Fluconazole (generic)
2. Fluconazole_shortage → affects patients currently prescribed Fluconazole
3. PT-002 -[PRESCRIBED]-> Fluconazole → has Warfarin interaction risk → shortage means must use alternative
4. PT-003 -[PRESCRIBED]-> Fluconazole → Tacrolimus interaction → echinocandin preferred anyway
5. PT-004 -[PRESCRIBED]-> Fluconazole → multiple interactions → shortage forces safer alternative
6. PT-005 -[PRESCRIBED]-> Fluconazole → Glipizide interaction risk → shortage may prevent harm (CASE-003 type event)
7. Alternative supply: Aurobindo Pharma also manufactures fluconazole → partial supply available
8. Echinocandins: Not manufactured by Teva → unaffected by Teva shutdown → clinically acceptable alternatives

**Correct graph answer:** Four patients in registry are prescribed fluconazole. Teva shutdown reduces supply but Aurobindo provides alternative source. Clinically, the shortage has mixed effects: prevents potential harm in PT-005 (fluconazole+glipizide interaction), forces safer alternatives for PT-003 and PT-004 where echinocandins are actually preferred.

---

## Node Count Target
Documents 1 through 12 should generate approximately the following nodes:
- Drug nodes: ~20
- Enzyme/transporter nodes: ~12
- Condition nodes: ~12
- Patient nodes: ~10
- Physician nodes: ~6
- Hospital nodes: ~3
- Pharmacist nodes: ~2
- Manufacturer nodes: ~10
- Protocol nodes: ~8
- Case/Event nodes: ~7
- Interaction/Contraindication nodes: ~15
- Total unique nodes: ~105 core nodes
- With all relationship endpoint nodes and property-derived nodes: ~500 total
