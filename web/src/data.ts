export type Page =
  "overview" | "hospitals" | "fields" | "identity" | "patients" | "help";
export type ReviewDecision = "approved" | "rejected";
export type Hospital = {
  id: string;
  name: string;
  location: string;
  system: string;
  stage: string;
};
export const hospitals: Hospital[] = [
  {
    id: "meghna",
    name: "Meghna General Hospital",
    location: "Dhaka",
    system: "OpenMRS",
    stage: "Ready for review",
  },
  {
    id: "padma",
    name: "Padma Care Hospital",
    location: "Chattogram",
    system: "OpenEMR",
    stage: "Ready for review",
  },
];
export const fields = [
  {
    id: "gender",
    hospital: "Meghna General Hospital",
    system: "OpenMRS",
    title: "Patient gender",
    source: "sex_cd",
    example: "F",
    target: "Female",
    meaning:
      "Turn the hospital’s gender codes into words every system understands.",
    reason: "The sample uses M for male, F for female, and U for unknown.",
    alternatives: ["M → Male", "F → Female", "U → Unknown"],
    technical: "Patient.gender",
    level: "Clear meaning",
  },
  {
    id: "name",
    hospital: "Padma Care Hospital",
    system: "OpenEMR",
    title: "Patient name",
    source: "fname",
    example: "Amina",
    target: "Given name: Amina",
    meaning: "Keep the patient’s given name in the right part of their record.",
    reason:
      "This field contains given names. The family name is stored in a separate field.",
    alternatives: [
      "Given name → Amina",
      "Family name → Rahman",
      "Display name → Amina Rahman",
    ],
    technical: "Patient.name[].given[]",
    level: "Clear meaning",
  },
  {
    id: "date",
    hospital: "Padma Care Hospital",
    system: "OpenEMR",
    title: "Date of birth",
    source: "DOB",
    example: "03/04/1988",
    target: "Needs clarification",
    meaning: "Confirm whether the hospital writes the month or the day first.",
    reason:
      "This date could mean 3 April or 4 March. More evidence is needed before using it.",
    alternatives: ["Day first → 3 April 1988", "Month first → 4 March 1988"],
    technical: "Patient.birthDate",
    level: "Needs attention",
  },
];
export const timeline = [
  {
    id: "visit",
    date: "22 Sep 2026",
    title: "Follow-up appointment",
    kind: "Appointment",
    hospital: "Meghna General Hospital",
    system: "OpenMRS",
    detail: "Routine follow-up with the outpatient care team.",
    value: "Completed",
    sourceId: "DEMO-A-1042",
    recordId: "DEMO-VISIT-208",
    mapping: "Preview release 1",
    icon: "visit",
  },
  {
    id: "bp",
    date: "22 Sep 2026",
    title: "Blood pressure",
    kind: "Measurement",
    hospital: "Meghna General Hospital",
    system: "OpenMRS",
    detail: "Recorded during the follow-up appointment.",
    value: "118/76 mmHg",
    sourceId: "DEMO-A-1042",
    recordId: "DEMO-OBS-352",
    mapping: "Preview release 1",
    icon: "measurement",
  },
  {
    id: "lab",
    date: "08 Sep 2026",
    title: "Blood glucose test",
    kind: "Lab result",
    hospital: "Padma Care Hospital",
    system: "OpenEMR",
    detail: "Fasting blood glucose measurement.",
    value: "5.1 mmol/L",
    sourceId: "DEMO-B-9928",
    recordId: "DEMO-LAB-149",
    mapping: "Preview release 1",
    icon: "lab",
  },
  {
    id: "consult",
    date: "08 Sep 2026",
    title: "Outpatient consultation",
    kind: "Appointment",
    hospital: "Padma Care Hospital",
    system: "OpenEMR",
    detail: "Initial outpatient consultation. Follow-up recommended.",
    value: "Completed",
    sourceId: "DEMO-B-9928",
    recordId: "DEMO-VISIT-102",
    mapping: "Preview release 1",
    icon: "visit",
  },
];
