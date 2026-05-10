export type StepId = "upload" | "style" | "review" | "modules" | "preview";

export type UploadSlot = "product_image" | "reports" | "documents";

export type StyleSource = "preset" | "ai_custom";

export type GenerationMode = "reference_generate" | "fixed_product_composite";

export type StyleOption = {
  id: string;
  name: string;
  keywords: string[];
  primary_color: string;
  asset: string;
  visual_direction?: string;
  layout_guidance?: string;
  reasoning?: string;
};

export type ImageGroup = "main" | "campaign" | "detail";

export type CommercePlatformId = "tmall" | "jd" | "douyin" | "pdd" | "xiaohongshu_square" | "xiaohongshu_portrait";

export type CommercePlatform = {
  id: CommercePlatformId;
  name: string;
  mainSize: string;
  generationSize: string;
  detailWidth: number;
  note: string;
};

export type ComplianceStatus = "pass" | "review" | "warn" | "block";
export type ComplianceSeverity = "review" | "warn" | "block";

export type ComplianceSummary = {
  status: ComplianceStatus;
  block_count: number;
  warn_count: number;
  review_count: number;
};

export type ComplianceIssue = {
  id?: string;
  severity?: ComplianceSeverity;
  category?: string;
  platform_ids?: CommercePlatformId[];
  term: string;
  matched_text?: string;
  location?: {
    source_type?: string;
    module_id?: string;
    field?: string;
    language?: string;
    image_index?: number;
    block_index?: number;
    image_url?: string;
    box?: number[];
  };
  reason?: string;
  suggestion?: string;
  qualification_hint?: string;
};

export type ComplianceReport = {
  source: string;
  ocr_source?: string;
  summary: ComplianceSummary;
  issues: ComplianceIssue[];
  ignored_matches?: Array<{ term: string; text: string; reason: string }>;
  extracted_texts?: Array<{
    text: string;
    confidence?: number;
    box?: number[] | null;
    location?: ComplianceIssue["location"];
  }>;
  image_count?: number;
  warnings?: string[];
};

export type ComplianceTextItem = {
  text: string;
  location: {
    source_type: string;
    module_id?: string;
    field?: string;
    language?: string;
  };
};

export type ModuleConfig = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  order: number;
  image_group?: ImageGroup;
};

export type ProductInfo = {
  product_name: string;
  category: string;
  spec: string;
  core_selling_points: string[];
  functions: string[];
  ingredients: Array<{ name: string; benefit: string }>;
  target_users: string[];
  usage_method: string[];
  authority_assets: string[];
  effect_claims: Array<{ claim: string; value: string; source_type: string }>;
  material_highlights?: string[];
  confirmation_status: "pending" | "confirmed";
};

export type UploadedFileInfo = {
  id: string;
  slot: UploadSlot;
  name: string;
  size: number;
  type: string;
  lastModified: number;
  dataUrl?: string;
  text?: string;
};

export type GeneratedImageVersion = {
  id: string;
  module_id: string;
  url: string;
  baseUrl?: string;
  textLayers?: TextLayer[];
  languageVersions?: LanguageVersionState;
  selectedLanguage?: LanguageCode;
  compliance?: ComplianceReport;
  label: string;
  source: string;
  createdAt: number;
  editInstruction?: string;
};

export type GeneratedImageVersionState = Record<string, GeneratedImageVersion[]>;

export type ProjectTemplate = {
  id: string;
  name: string;
  category: string;
  styleId: string;
  platformId: CommercePlatformId;
  modules: Array<{ id: string; enabled: boolean; order: number }>;
  source: "official" | "user";
};

export type MaterialPayload = {
  slot: UploadSlot;
  filename: string;
  content_type: string;
  data_url?: string;
  text?: string;
};

export type PublicModelConfig = {
  textAnalysis: {
    model: string;
    configured: boolean;
    defaults: {
      max_tokens: number;
      temperature: number;
    };
  };
  imageGeneration: {
    model: string;
    configured: boolean;
    defaultOptionId?: string;
    options?: Array<{
      id: string;
      label: string;
      model: string;
      configured: boolean;
      defaults: {
        size: string;
        n: number;
        quality?: string;
        output_format?: string;
        response_format?: string;
      };
    }>;
    defaults: {
      size: string;
      n: number;
      quality?: string;
      output_format?: string;
      response_format?: string;
    };
    fallback?: {
      model: string;
      configured: boolean;
      defaults: {
        size: string;
        n: number;
      };
    };
  };
};

export type GeneratedImage = { module_id: string; url: string; compliance?: ComplianceReport };

export type LanguageCode = "zh-CN" | "en" | "th" | "ms";

export type TextLayer = {
  id: string;
  role: string;
  source_text?: string;
  text: string;
  x: number;
  y: number;
  width: number;
  height: number;
  font_size: number;
  color?: string;
  align?: "left" | "center" | "right";
  max_lines?: number;
  weight?: "regular" | "bold";
};

export type LanguageVersion = {
  language: LanguageCode;
  language_label: string;
  url: string;
  layers?: TextLayer[];
  warnings?: string[];
  compliance?: ComplianceReport;
  createdAt?: number;
};

export type LanguageVersionState = Partial<Record<LanguageCode, LanguageVersion>>;

export type PersistedProjectState = {
  projectStateSchemaVersion?: number;
  productInfo: ProductInfo | null;
  hasAiProductInfo: boolean;
  uploadedFiles: UploadedFileInfo[];
  selectedStyleId: string;
  customStyle: StyleOption | null;
  styleSource: StyleSource;
  selectedCategory: string;
  selectedPlatformId: CommercePlatformId;
  selectedImageModelId?: string;
  generationMode: GenerationMode;
  activeImageGroup: ImageGroup;
  promotionInfo: string;
  modules: ModuleConfig[];
  generatedImages: GeneratedImage[];
  generatedImageVersions: GeneratedImageVersionState;
  selectedVersionIds: Record<string, string>;
  userTemplates: ProjectTemplate[];
  statusText: string;
};
