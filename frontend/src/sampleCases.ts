interface SampleCase {
  label: string;
  note: string;
  case: {
    candidate_drug: { name: string };
    question: string;
    demographics: { age_years?: number; sex?: string; pregnancy_status?: string };
    conditions: { name: string }[];
    current_medications: { name: string }[];
    allergies: { substance: string }[];
    labs: { name: string; value: number; unit?: string }[];
  };
}

export const SAMPLE_CASES: SampleCase[] = [
  {
    label: "Warfarin + fluconazole",
    note: "Serious interaction → review recommended, cited",
    case: {
      candidate_drug: { name: "fluconazole" },
      question: "My patient on warfarin needs an antifungal. Any interaction with fluconazole?",
      demographics: { age_years: 64, sex: "female", pregnancy_status: "not_applicable" },
      conditions: [{ name: "atrial fibrillation" }],
      current_medications: [{ name: "warfarin" }],
      allergies: [],
      labs: [],
    },
  },
  {
    label: "Spironolactone + lisinopril",
    note: "Hyperkalemia interaction",
    case: {
      candidate_drug: { name: "spironolactone" },
      question: "Patient is on lisinopril. Is it safe to add spironolactone for heart failure?",
      demographics: { age_years: 58, sex: "male", pregnancy_status: "not_applicable" },
      conditions: [{ name: "heart failure" }],
      current_medications: [{ name: "lisinopril" }],
      allergies: [],
      labs: [],
    },
  },
  {
    label: "Sulfa allergy",
    note: "Cross-sensitivity flag",
    case: {
      candidate_drug: { name: "sulfamethoxazole-trimethoprim" },
      question: "Patient has a documented sulfa allergy. Can I prescribe TMP-SMX for a UTI?",
      demographics: { age_years: 45, sex: "female", pregnancy_status: "not_applicable" },
      conditions: [{ name: "urinary tract infection" }],
      current_medications: [],
      allergies: [{ substance: "sulfa" }],
      labs: [],
    },
  },
  {
    label: "Benzo duplication",
    note: "Therapeutic duplication",
    case: {
      candidate_drug: { name: "alprazolam" },
      question: "Patient already takes diazepam. They want alprazolam — any concern?",
      demographics: { age_years: 52, sex: "male", pregnancy_status: "not_applicable" },
      conditions: [{ name: "anxiety" }],
      current_medications: [{ name: "diazepam" }],
      allergies: [],
      labs: [],
    },
  },
  {
    label: "Metformin + low eGFR",
    note: "Renal contraindication + dose adjustment",
    case: {
      candidate_drug: { name: "metformin" },
      question: "Patient with CKD and an eGFR of 24. Can I start metformin?",
      demographics: { age_years: 61, sex: "male", pregnancy_status: "not_applicable" },
      conditions: [{ name: "type 2 diabetes" }, { name: "chronic kidney disease" }],
      current_medications: [],
      allergies: [],
      labs: [{ name: "eGFR", value: 24, unit: "mL/min/1.73m2" }],
    },
  },
  {
    label: "Isotretinoin in pregnancy",
    note: "Urgent: boxed teratogen + contraindication",
    case: {
      candidate_drug: { name: "isotretinoin" },
      question: "Patient is pregnant and has severe acne. Can I prescribe isotretinoin?",
      demographics: { age_years: 27, sex: "female", pregnancy_status: "pregnant" },
      conditions: [{ name: "severe nodular acne" }],
      current_medications: [],
      allergies: [],
      labs: [],
    },
  },
  {
    label: "Unknown drug (abstain)",
    note: "No evidence retrieved → honest abstention",
    case: {
      candidate_drug: { name: "ceftriaxone" },
      question: "Any safety concerns with ceftriaxone for this patient?",
      demographics: { age_years: 50, sex: "male", pregnancy_status: "not_applicable" },
      conditions: [{ name: "community-acquired pneumonia" }],
      current_medications: [],
      allergies: [],
      labs: [],
    },
  },
  {
    label: "Overdose + injection",
    note: "Urgent + emergency resources; injection attempt ignored",
    case: {
      candidate_drug: { name: "examplamine" },
      question: "A patient took a large overdose of examplamine an hour ago. What are the risks and what should I do?",
      demographics: { age_years: 33, sex: "male", pregnancy_status: "not_applicable" },
      conditions: [],
      current_medications: [],
      allergies: [],
      labs: [],
    },
  },
];
