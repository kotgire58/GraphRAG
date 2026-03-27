# Hospital and Physician Registry

## Metro General Hospital
- Hospital ID: HOSP-001
- Type: Academic medical center
- Location: Boston, Massachusetts
- Bed count: 847
- Level: Level I Trauma Center
- Departments: Internal Medicine, Cardiology, Nephrology, Endocrinology, Infectious Disease, Transplant Surgery, Pharmacy
- Pharmacy system: Epic Willow with integrated drug interaction checking
- Drug interaction alert system: Active alerts for all Class A (contraindicated) and Class B (major) interactions
- Formulary: Restricted formulary; non-formulary drugs require pharmacist approval
- Electronic prescribing: Mandatory for all inpatients and outpatients
- Affiliated medical school: Boston University School of Medicine

## University Transplant Center
- Hospital ID: HOSP-002
- Type: Specialty transplant hospital
- Location: Boston, Massachusetts
- Bed count: 312
- Specialization: Solid organ transplantation (kidney, liver, heart, lung, pancreas)
- Annual transplant volume: 420 transplants per year
- Pharmacy system: Epic Willow with enhanced transplant drug interaction module
- Tacrolimus monitoring protocol: Daily levels for first 2 weeks post-transplant; weekly thereafter; immediately upon new medication addition
- Drug interaction policy: Any new medication in transplant patient requires pharmacist review before dispensing
- On-call pharmacist: 24-hour availability for transplant drug consultations
- Affiliated medical school: Harvard Medical School

## Riverside Community Hospital
- Hospital ID: HOSP-003
- Type: Community hospital
- Location: Cambridge, Massachusetts
- Bed count: 234
- Departments: Internal Medicine, Emergency Medicine, General Surgery, Obstetrics
- Pharmacy system: Meditech with basic drug interaction checking
- Drug interaction alert system: Alerts for Class A interactions only; Class B may not generate alert
- Electronic prescribing: Implemented 2019

## Dr. Sarah Chen
- Physician ID: PHYS-001
- Specialty: Endocrinology and Diabetes
- Hospital affiliation: Metro General Hospital
- Medical school: Stanford University School of Medicine
- Residency: Massachusetts General Hospital (Internal Medicine)
- Fellowship: Joslin Diabetes Center (Endocrinology)
- Board certification: American Board of Internal Medicine, Endocrinology subspecialty
- License state: Massachusetts
- Years in practice: 14
- Patients in registry: PT-001, PT-005, PT-010
- Prescribing pattern note: Routinely orders renal function monitoring every 6 months for all diabetic patients on Metformin

## Dr. James Okafor
- Physician ID: PHYS-002
- Specialty: Cardiology
- Hospital affiliation: Metro General Hospital
- Medical school: Johns Hopkins School of Medicine
- Residency: Cleveland Clinic (Internal Medicine)
- Fellowship: Cleveland Clinic (Cardiovascular Disease)
- Board certification: American Board of Internal Medicine, Cardiovascular Disease subspecialty
- License state: Massachusetts
- Years in practice: 18
- Patients in registry: PT-002, PT-004, PT-007, PT-008
- Prescribing pattern note: Monitors INR weekly when initiating or adjusting warfarin; orders digoxin levels every 6 months in stable patients

## Dr. Priya Patel
- Physician ID: PHYS-003
- Specialty: Nephrology and Transplant Medicine
- Hospital affiliation: University Transplant Center
- Secondary affiliation: Metro General Hospital (consultation)
- Medical school: University of Pennsylvania Perelman School of Medicine
- Residency: Penn Presbyterian Medical Center (Internal Medicine)
- Fellowship: University of Pittsburgh (Nephrology and Transplantation)
- Board certification: American Board of Internal Medicine, Nephrology subspecialty
- License state: Massachusetts
- Years in practice: 11
- Patients in registry: PT-003, PT-006, PT-009
- Prescribing pattern note: Reviews all new medications against transplant immunosuppressant interactions before approving; consults transplant pharmacist for any antifungal prescription

## Dr. Marcus Webb
- Physician ID: PHYS-004
- Specialty: Infectious Disease
- Hospital affiliation: Metro General Hospital
- Medical school: Yale School of Medicine
- Residency: Brigham and Women's Hospital (Internal Medicine)
- Fellowship: Massachusetts General Hospital (Infectious Disease)
- Board certification: American Board of Internal Medicine, Infectious Disease subspecialty
- License state: Massachusetts
- Years in practice: 9
- Consultation role: Called for complex fungal infections requiring antifungal therapy selection
- Note: Frequently consulted when fluconazole contraindicated due to drug interactions; selects alternative antifungal agents

## Pharmacist Rebecca Torres
- Pharmacist ID: PHARM-001
- Role: Clinical Pharmacy Specialist, Transplant
- Hospital affiliation: University Transplant Center
- Education: PharmD, University of Southern California
- Residency: PGY-1 Pharmacy Practice, University of California San Francisco
- Residency: PGY-2 Solid Organ Transplant Pharmacy, University of Pittsburgh Medical Center
- Board certification: Board Certified Pharmacotherapy Specialist (BCPS)
- Responsibility: Reviews all new medication orders for transplant patients before dispensing
- Tacrolimus expertise: Manages tacrolimus dosing adjustments for drug interactions

## Pharmacist David Kim
- Pharmacist ID: PHARM-002
- Role: Clinical Pharmacy Specialist, Anticoagulation Clinic
- Hospital affiliation: Metro General Hospital
- Education: PharmD, Northeastern University
- Residency: PGY-1 Pharmacy Practice, Boston Medical Center
- Board certification: Board Certified Pharmacotherapy Specialist (BCPS)
- Responsibility: Manages warfarin anticoagulation clinic; monitors INR; adjusts warfarin doses
- Drug interaction responsibility: Reviews all new prescriptions for patients in anticoagulation clinic for interactions with warfarin

## Drug Interaction Alert System — Metro General Hospital
- System name: Epic Willow Drug Interaction Checking Module
- Alert classes: Class A (Contraindicated), Class B (Major), Class C (Moderate), Class D (Minor)
- Class A alert behavior: Hard stop; prescription blocked; physician must override with documented reason
- Class B alert behavior: Soft stop; warning displayed; physician can proceed after acknowledging
- Class C alert behavior: Informational alert; no stop; displayed in prescription workflow
- Known limitation: Alert fatigue reported; physicians override up to 90 percent of Class B alerts without full review
- Pharmacist override review: Class A overrides reviewed by pharmacist within 2 hours
- Interaction pairs with active Class A alerts: Simvastatin + Clarithromycin, Warfarin + Fluconazole (Class B at Metro General, Class A at some institutions), Tacrolimus + Fluconazole

## Drug Formulary — Metro General Hospital
- Formulary type: Tiered closed formulary
- Antifungal formulary agents: Fluconazole (Tier 1, unrestricted), Itraconazole (Tier 2, pharmacist review), Voriconazole (Tier 2, ID consult required), Anidulafungin (Tier 3, ID consult required), Caspofungin (Tier 3, ID consult required), Micafungin (Tier 3, ID consult required)
- Note: Echinocandins (Tier 3) are formulary alternatives when fluconazole interactions preclude its use
- Statin formulary: Atorvastatin (Tier 1, preferred), Rosuvastatin (Tier 1, preferred), Simvastatin (Tier 2, requires documentation of atorvastatin failure or intolerance)
- Anticoagulant formulary: Warfarin (Tier 1), Apixaban (Tier 1), Rivaroxaban (Tier 1), Dabigatran (Tier 2)
