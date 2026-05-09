export type StepId = "upload" | "style" | "review" | "modules" | "preview";

export type UploadSlot = "product_image" | "reports" | "documents";

export type StyleSource = "preset" | "ai_custom";

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

export type GeneratedImage = { module_id: string; url: string };

export type PersistedProjectState = {
  productInfo: ProductInfo | null;
  hasAiProductInfo: boolean;
  uploadedFiles: UploadedFileInfo[];
  selectedStyleId: string;
  customStyle: StyleOption | null;
  styleSource: StyleSource;
  selectedCategory: string;
  selectedPlatformId: CommercePlatformId;
  selectedImageModelId?: string;
  activeImageGroup: ImageGroup;
  promotionInfo: string;
  modules: ModuleConfig[];
  generatedImages: GeneratedImage[];
  generatedImageVersions: GeneratedImageVersionState;
  selectedVersionIds: Record<string, string>;
  userTemplates: ProjectTemplate[];
  statusText: string;
};
