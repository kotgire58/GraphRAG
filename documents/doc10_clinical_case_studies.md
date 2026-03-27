# Clinical Case Studies — Adverse Drug Event Records

## Case ID: CASE-001
- Case type: Adverse drug event — drug interaction
- Patient ID: PT-002 (72-year-old female, Atrial Fibrillation, Hypertension, CAD)
- Reporting physician: Dr. James Okafor
- Hospital: Metro General Hospital
- Date of event: Day 5 after fluconazole prescription
- Precipitating prescription: Fluconazole 150mg single dose prescribed for vaginal candidiasis
- Concurrent medication at time of event: Warfarin 5mg daily (INR was 2.3 at baseline)
- Event description: Patient presented to emergency department with gum bleeding and easy bruising
- INR at presentation: 4.8 (above therapeutic range of 2.0 to 3.0; bleeding risk zone above 4.0)
- Management: Warfarin held; vitamin K 2.5mg oral administered; INR rechecked 24 hours later (3.1); warfarin restarted at reduced dose 3mg daily
- Root cause: Fluconazole CYP2C9 inhibition increased warfarin levels; INR monitoring not performed after fluconazole
- Preventability: Yes — mandatory INR check within 2 to 3 days of fluconazole initiation not ordered
- Outcome: Patient recovered without serious harm; warfarin dose adjusted
- Pharmacist review: Completed retrospectively; fluconazole-warfarin interaction was in Epic system as Class B alert; physician acknowledged alert without acting
- Learning: Alert fatigue identified; Class B alert for fluconazole-warfarin upgraded to require pharmacist co-sign

## Case ID: CASE-002
- Case type: Adverse drug event — drug interaction (near miss)
- Patient ID: PT-003 (45-year-old male, kidney transplant, on Tacrolimus)
- Reporting physician: Dr. Priya Patel
- Hospital: University Transplant Center
- Date of event: Intercepted before dispensing
- Precipitating prescription: Fluconazole 200mg daily for 7 days prescribed by covering physician unfamiliar with transplant protocols
- Concurrent medication: Tacrolimus 3mg twice daily (trough 7.2 ng/mL)
- Pharmacist action: Pharmacist Rebecca Torres identified interaction before dispensing; contacted Dr. Patel
- Projected consequence if dispensed: Tacrolimus levels would have risen to estimated 14 to 28 ng/mL (toxic range above 15 ng/mL); nephrotoxicity and neurotoxicity expected
- Management: Fluconazole held; Caspofungin 70mg loading dose then 50mg daily prescribed instead (echinocandin, no CYP3A4 interaction)
- Outcome: Near miss; no patient harm
- System finding: Covering physician not aware of transplant drug interaction protocols
- Change implemented: All fluconazole prescriptions for transplant patients now require transplant pharmacist approval before dispensing

## Case ID: CASE-003
- Case type: Adverse drug event — drug interaction
- Patient ID: PT-005 (52-year-old male, Type 2 Diabetes, on Glipizide and Metformin)
- Reporting physician: Dr. Sarah Chen
- Hospital: Metro General Hospital
- Date of event: Day 3 of fluconazole course
- Precipitating prescription: Fluconazole 150mg weekly for 12 weeks prescribed for nail fungal infection
- Concurrent medication: Glipizide 5mg twice daily, Metformin 500mg twice daily
- Event description: Patient found unconscious at home; blood glucose 32 mg/dL (severe hypoglycemia)
- Emergency response: 911 called; paramedics administered IV dextrose; patient responsive within 5 minutes
- Hospital admission: Yes; 24 hours for monitoring
- Root cause: Fluconazole CYP2C9 inhibition reduced glipizide clearance; glipizide accumulated; prolonged hypoglycemia
- Aggravating factor: Patient had skipped lunch that day
- Management: Glipizide held during fluconazole course; metformin continued; blood glucose monitoring twice daily
- Alternative considered: Terbinafine (not CYP2C9 dependent) for nail fungal infection instead of fluconazole
- Outcome: Full recovery; glipizide replaced with sitagliptin (DPP-4 inhibitor, no hypoglycemia risk)
- Preventability: Yes — fluconazole-sulfonylurea interaction known; patient counseling on hypoglycemia signs not provided

## Case ID: CASE-004
- Case type: Adverse drug event — drug interaction
- Patient ID: PT-008 (70-year-old female, Atrial Fibrillation, Heart Failure, on Amiodarone, Warfarin, Digoxin)
- Reporting physician: Dr. James Okafor
- Hospital: Metro General Hospital
- Date of event: Day 10 of fluconazole course
- Precipitating prescription: Fluconazole 200mg daily for systemic candidiasis
- Concurrent medications at time of event: Amiodarone 200mg daily, Warfarin 3mg daily (INR 2.8 baseline), Digoxin 0.125mg daily (level 1.1 ng/mL baseline)
- Multi-drug interaction cascade:
  - Interaction 1: Fluconazole inhibits CYP2C9; warfarin clearance reduced; INR rises
  - Interaction 2: Fluconazole inhibits CYP3A4; amiodarone partially metabolized by CYP3A4; amiodarone levels rise
  - Interaction 3: Amiodarone inhibits P-gp; digoxin clearance reduced; digoxin levels rise
  - Interaction 4: Fluconazole and amiodarone both prolong QT interval; additive QT prolongation
- Event description: Patient developed nausea, visual halos, and irregular palpitations on day 10
- Laboratory findings at presentation: INR 6.2 (dangerously elevated), Digoxin level 2.4 ng/mL (toxic above 2.0), QTc 520ms (prolonged, normal below 440ms in women)
- Arrhythmia finding: Torsades de pointes on ECG monitoring
- Management: Fluconazole switched to Anidulafungin IV (no CYP interactions); Warfarin held; Digoxin held; Magnesium sulfate IV for torsades; overdrive pacing available as backup
- ICU admission: Yes; 3 days
- Outcome: Patient stabilized; discharged day 14; digoxin not restarted; warfarin restarted at lower dose with frequent INR monitoring
- Root cause: Three-way interaction not individually flagged by alert system as combined risk; alert system evaluates drug pairs, not combinations
- System limitation identified: Drug interaction checking systems evaluate binary pairs; do not model multi-drug cascade interactions

## Case ID: CASE-005
- Case type: Adverse drug event — condition-drug interaction
- Patient ID: PT-001 (58-year-old male, Type 2 Diabetes, Hypertension, on Metformin, Lisinopril, Atorvastatin)
- Reporting physician: Dr. Sarah Chen
- Hospital: Metro General Hospital
- Date of event: 3 days after CT scan with IV contrast
- Precipitating procedure: CT abdomen with IV contrast for suspected appendicitis
- Concurrent medication: Metformin 1000mg twice daily
- Protocol failure: Metformin not held before or after contrast procedure; emergency situation led to protocol oversight
- GFR at baseline: 62 mL/min/1.73m2
- GFR post-contrast: Dropped to 41 mL/min/1.73m2 (contrast-induced nephropathy)
- Event description: Patient presented with nausea, vomiting, abdominal pain, and hyperventilation 3 days post-procedure
- Laboratory findings: Serum lactate 7.2 mmol/L (severe lactic acidosis, normal below 2.0), pH 7.18 (severe acidosis)
- Diagnosis: Metformin-associated lactic acidosis (MALA) secondary to contrast-induced nephropathy and metformin continuation
- Management: ICU admission; IV bicarbonate; IV fluids; hemodialysis to remove metformin; supportive care
- ICU stay: 5 days
- Outcome: Full recovery; metformin dose reduced and renal function monitoring increased post-discharge
- Root cause: Metformin not held per contrast protocol; compounded by underlying CKD stage 3 reducing baseline clearance
- Preventability: Yes — standard protocol requires metformin hold before and after IV contrast; emergency setting created protocol gap

## Case ID: CASE-006
- Case type: Potential adverse event — prescribing review (no event occurred)
- Patient ID: PT-001 (58-year-old male, Type 2 Diabetes, Hypertension, on Metformin, Lisinopril, Atorvastatin)
- Reviewing pharmacist: Pharmacist David Kim (noted during routine medication reconciliation)
- Trigger: Patient presenting with oral candidiasis; Dr. Sarah Chen considering Fluconazole 150mg single dose
- Review finding 1: Fluconazole has no direct pharmacokinetic interaction with Metformin (different enzyme pathways); Metformin cleared by OCT2/MATE transporters, not CYP2C9 or CYP3A4
- Review finding 2: Fluconazole has no direct pharmacokinetic interaction with Lisinopril; Lisinopril not hepatically metabolized
- Review finding 3: Fluconazole inhibits CYP3A4 moderately; Atorvastatin metabolized by CYP3A4; single low dose fluconazole unlikely to cause clinically significant atorvastatin accumulation
- Review finding 4: Patient GFR 62 mL/min/1.73m2; Fluconazole dose adjustment not required until GFR below 50
- Overall assessment: Fluconazole 150mg single dose is SAFE for this patient's specific medication combination
- Recommendation: Prescribe as planned; no dose adjustments needed; monitor for muscle symptoms if atorvastatin dose is high
- Note: This case demonstrates that not all patients on Metformin and Lisinopril have a contraindication to fluconazole; interaction risk depends on complete medication list and patient-specific factors
- Contrast with CASE-003: PT-005 had Glipizide (sulfonylurea, CYP2C9 substrate) making fluconazole dangerous; PT-001 does not have sulfonylurea

## Case ID: CASE-007
- Case type: Adverse drug event — disease-drug interaction
- Patient ID: PT-007 (55-year-old male, CAD with stent, Type 2 Diabetes, on Clopidogrel, Metformin, Lisinopril, Rosuvastatin)
- Reporting physician: Dr. James Okafor
- Hospital: Metro General Hospital
- Event: Stent thrombosis 8 months after stent placement
- Precipitating factor: Omeprazole 20mg daily prescribed by gastroenterologist for heartburn 3 months prior without cardiology notification
- Mechanism: Omeprazole inhibits CYP2C19; clopidogrel requires CYP2C19 activation; reduced active clopidogrel metabolite; inadequate platelet inhibition
- Laboratory finding: Platelet function testing showed high on-treatment platelet reactivity (clopidogrel non-response)
- Event: Stent thrombosis; acute myocardial infarction; emergency PCI required
- Genetic finding post-event: Patient found to be CYP2C19 intermediate metabolizer (one loss-of-function allele); compounded effect of omeprazole
- Management: Emergency PCI; clopidogrel replaced with ticagrelor (not dependent on CYP2C19 activation); omeprazole replaced with pantoprazole (minimal CYP2C19 inhibition)
- Outcome: Survived; LVEF reduced to 45 percent; ongoing cardiology follow-up
- Root cause: Prescribing siloed between gastroenterology and cardiology; no shared medication review; omeprazole-clopidogrel interaction not flagged across departments
- System failure: Different specialty EMR modules not integrated for cross-specialty drug interaction checking
