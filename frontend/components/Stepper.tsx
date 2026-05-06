import { ArrowRight } from "lucide-react";
import type { StepId } from "@/lib/types";

const steps: Array<{ id: StepId; label: string }> = [
  { id: "upload", label: "上传资料" },
  { id: "review", label: "确认信息" },
  { id: "style", label: "选择风格" },
  { id: "modules", label: "选择模块" },
  { id: "preview", label: "预览导出" }
];

export function Stepper({ activeStep, onStepChange }: { activeStep: StepId; onStepChange: (step: StepId) => void }) {
  return (
    <nav className="stepper" aria-label="生成流程">
      {steps.map((step, index) => (
        <div className="stepperItem" key={step.id}>
          <button className={`stepButton ${activeStep === step.id ? "active" : ""}`} onClick={() => onStepChange(step.id)}>
            <span>{index + 1}</span>
            {step.label}
          </button>
          {index < steps.length - 1 ? <ArrowRight className="stepArrow" size={24} /> : null}
        </div>
      ))}
    </nav>
  );
}
