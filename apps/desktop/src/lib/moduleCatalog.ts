import { ClipboardList, FileSpreadsheet, GraduationCap, UserPlus } from "lucide-react";

export type ModuleId = "formConverter" | "studentBasicInfo" | "currentStudents" | "graduation";
export type ModuleStatus = "skeleton" | "ready";

export type ModuleContract = {
  version: string;
  inputs: string[];
  validations: string[];
  outputs: string[];
  events: string[];
};

export type ModuleDefinition = {
  id: ModuleId;
  status: ModuleStatus;
  icon: typeof GraduationCap;
  requiresCredits: boolean;
  pricingMode: "per_billable_record";
  creditPerUnit: number;
  productionDryRunEnabled: boolean;
  contract: ModuleContract;
};

export const moduleDefinitions: ModuleDefinition[] = [
  {
    id: "formConverter",
    status: "ready",
    icon: FileSpreadsheet,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 3,
    productionDryRunEnabled: false,
    contract: {
      version: "0.2",
      inputs: [
        "student_roster_excel_path",
        "thai_id_csv_path",
        "ocr_markdown_paths",
        "civil_registration_markdown_paths",
        "school_year",
        "grade_levels",
      ],
      validations: ["roster_sheet_structure", "thai_id_format", "thai_id_checksum", "field_provenance"],
      outputs: ["dmc_form_json_path", "match_summary", "warnings"],
      events: ["export_dmc_form_json"],
    },
  },
  {
    id: "studentBasicInfo",
    status: "ready",
    icon: ClipboardList,
    requiresCredits: false,
    pricingMode: "per_billable_record",
    creditPerUnit: 0,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1",
      inputs: ["dmc_student_excel_path", "student_basic_info_template"],
      validations: ["dmc_header_row", "required_columns_present", "classroom_grouping"],
      outputs: ["student_basic_info_workbook_path", "class_sheets", "export_summary"],
      events: ["export_student_basic_info_form"],
    },
  },
  {
    id: "currentStudents",
    status: "ready",
    icon: UserPlus,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 1,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1-draft",
      inputs: ["blank_current_students_template", "completed_current_students_excel_or_json_path"],
      validations: [
        "import_workbook_headers",
        "dmc_form_json_v1_schema",
        "required_columns_present",
        "required_fields_present",
        "dmc_transfer_in_required_fields",
        "dmc_transfer_in_level_mapping",
        "thai_id_format",
        "thai_id_checksum",
        "duplicate_student_check",
      ],
      outputs: ["validated_import_preview", "import_summary", "validation_warnings"],
      events: [
        "module_opened",
        "export_current_student_blank_form",
        "validate_current_student_import_form",
        "current_student_import_started",
        "current_student_import_completed",
      ],
    },
  },
  {
    id: "graduation",
    status: "ready",
    icon: GraduationCap,
    requiresCredits: true,
    pricingMode: "per_billable_record",
    creditPerUnit: 1,
    productionDryRunEnabled: false,
    contract: {
      version: "0.1",
      inputs: ["obec_study_excel_path", "grade_level", "minimum_match_score"],
      validations: ["excel_schema", "status_mapping", "browser_runtime", "credit_policy"],
      outputs: ["obec_fill_report_csv", "obec_fill_review_csv", "run_summary", "completion_summary_xlsx"],
      events: ["validate_excel", "start_job", "progress", "job_done"],
    },
  },
];

export function getModuleDefinition(id: ModuleId): ModuleDefinition {
  const module = moduleDefinitions.find((item) => item.id === id);
  if (!module) {
    throw new Error(`Unknown module: ${id}`);
  }
  return module;
}
