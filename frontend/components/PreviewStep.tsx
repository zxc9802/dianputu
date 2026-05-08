"use client";

import { useState } from "react";
import { Download, FileImage, Monitor, Smartphone } from "lucide-react";
import { createComposeLongImageJob, fetchComposeLongImageDownload, fetchComposeLongImageJob, prepareComposeLongImageSources } from "@/lib/api";
import type { CommercePlatform, GeneratedImageVersionState, ImageGroup, ModuleConfig } from "@/lib/types";

type GeneratedImage = { module_id: string; url: string };
type PreviewItem = { module: ModuleConfig; url: string };
type GenerationProgress = { isGenerating: boolean; completed: number; total: number; runningModuleIds: string[]; errorCount: number };
type GenerationProgressMap = Record<ImageGroup, GenerationProgress>;

const imageGroups: ImageGroup[] = ["main", "campaign", "detail"];

const groupCopy: Record<ImageGroup, { title: string; empty: string; directory: string }> = {
  main: { title: "主图预览", empty: "主图生成后会在这里按 5 张独立卡片展示。", directory: "主图目录" },
  campaign: { title: "活动主图预览", empty: "活动主图生成后会在这里按 5 张独立卡片展示。", directory: "活动主图目录" },
  detail: { title: "详情长图预览", empty: "详情图生成后会在这里按模块拼成完整长图。", directory: "详情图目录" }
};

const COMPOSE_TIMEOUT_MS = 600000;
const COMPOSE_POLL_INTERVAL_MS = 1000;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  downloadUrl(url, filename);
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function downloadUrl(url: string, filename: string) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function moduleGroup(module: ModuleConfig): ImageGroup {
  return module.image_group ?? "detail";
}

function sortedGroupModules(modules: ModuleConfig[], group: ImageGroup) {
  return modules.filter((module) => moduleGroup(module) === group).sort((a, b) => a.order - b.order);
}

function buildPreviewItems(modules: ModuleConfig[], generatedByModule: Map<string, string>) {
  return modules
    .map((module) => {
      const url = generatedByModule.get(module.id);
      return url ? { module, url } : null;
    })
    .filter((item): item is PreviewItem => Boolean(item));
}

export function PreviewStep({
  modules,
  activeImageGroup,
  generatedImages,
  imageVersions,
  selectedVersionIds,
  generationProgress,
  selectedPlatform,
  onImageGroupChange,
  onGenerateModule,
  onSelectVersion,
  onEditImage,
  onBack
}: {
  modules: ModuleConfig[];
  activeImageGroup: ImageGroup;
  generatedImages: GeneratedImage[];
  imageVersions: GeneratedImageVersionState;
  selectedVersionIds: Record<string, string>;
  generationProgress: GenerationProgressMap;
  selectedPlatform: CommercePlatform;
  onImageGroupChange: (group: ImageGroup) => void;
  onGenerateModule: (group: ImageGroup, moduleId: string) => void;
  onSelectVersion: (moduleId: string, versionId: string) => void;
  onEditImage: (moduleId: string, imageUrl: string, instruction: string) => void;
  onBack: () => void;
}) {
  const [isComposing, setIsComposing] = useState(false);
  const [composeStatus, setComposeStatus] = useState("");
  const [composeError, setComposeError] = useState("");
  const [editDrafts, setEditDrafts] = useState<Record<string, string>>({});
  const generatedByModule = new Map(generatedImages.map((image) => [image.module_id, image.url]));
  const groupedModules = {
    main: sortedGroupModules(modules, "main"),
    campaign: sortedGroupModules(modules, "campaign"),
    detail: sortedGroupModules(modules, "detail").filter((module) => module.enabled)
  };
  const groupedItems = {
    main: buildPreviewItems(groupedModules.main, generatedByModule),
    campaign: buildPreviewItems(groupedModules.campaign, generatedByModule),
    detail: buildPreviewItems(groupedModules.detail, generatedByModule)
  };
  const visibleModules = groupedModules[activeImageGroup];
  const visibleItems = groupedItems[activeImageGroup];
  const activeProgress = generationProgress[activeImageGroup];
  const detailManifest = groupedItems.detail.map((item) => ({
    module_id: item.module.id,
    module_name: item.module.name,
    url: item.url
  }));
  const manifestHref = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(detailManifest, null, 2))}`;
  const batchDownloadLabel = activeImageGroup === "campaign" ? "活动主图" : "主图";

  function handleDownloadVisibleBatch() {
    if (activeImageGroup === "detail" || visibleItems.length === 0) return;
    visibleItems.forEach((item, index) => {
      window.setTimeout(() => {
        downloadUrl(item.url, `${activeImageGroup}-${String(index + 1).padStart(2, "0")}-${item.module.id}.png`);
      }, index * 120);
    });
  }

  async function handleDownloadLongJpg() {
    if (isComposing || groupedItems.detail.length === 0) return;
    setIsComposing(true);
    setComposeError("");
    setComposeStatus("正在准备合成");
    try {
      setComposeStatus("正在上传合成素材");
      const prepared = await prepareComposeLongImageSources(detailManifest);
      setComposeStatus("正在创建合成任务");
      const { job_id: jobId } = await createComposeLongImageJob(prepared.images);
      const startedAt = Date.now();
      while (Date.now() - startedAt < COMPOSE_TIMEOUT_MS) {
        const status = await fetchComposeLongImageJob(jobId);
        setComposeStatus(status.message || "正在合成 JPG");
        if (status.status === "done") {
          const download = await fetchComposeLongImageDownload(jobId);
          if ("url" in download) {
            window.location.href = download.url;
          } else {
            downloadBlob(download.blob, "full-detail.jpg");
          }
          setComposeStatus("合成完成");
          return;
        }
        if (status.status === "error") {
          throw new Error(status.error || status.message || "长图合成失败");
        }
        await wait(COMPOSE_POLL_INTERVAL_MS);
      }
      throw new Error("长图合成超过 10 分钟，请稍后重试");
    } catch (error) {
      setComposeError(error instanceof Error ? error.message : "长图合成失败");
    } finally {
      setIsComposing(false);
    }
  }

  return (
    <>
      <div className="previewLayout">
        <section className="panel previewPanel">
          <div className="sectionTitle">
            <span>5</span>
            <div>
              <h2>{groupCopy[activeImageGroup].title}</h2>
              <p>主图、活动主图和详情图同页保留，可切换查看生成进度和结果。</p>
            </div>
          </div>

          <div className="groupTabs previewTabs" role="tablist" aria-label="预览版块">
            {imageGroups.map((group) => {
              const progress = generationProgress[group];
              const total = groupedModules[group].length;
              const loaded = groupedItems[group].length;
              return (
                <button
                  key={group}
                  className={activeImageGroup === group ? "groupTab active" : "groupTab"}
                  onClick={() => onImageGroupChange(group)}
                  type="button"
                >
                  <b>{groupCopy[group].title}</b>
                  <span>{groupCopy[group].empty}</span>
                  <em>{progress.isGenerating ? `并行生成中 ${progress.completed}/${progress.total}` : `已加载 ${loaded}/${total}`}</em>
                </button>
              );
            })}
          </div>

          <div className="previewToolbar">
            <Monitor size={20} />
            <Smartphone size={20} />
            <span>{activeImageGroup === "detail" ? `详情宽 ${selectedPlatform.detailWidth}px` : `主图 ${selectedPlatform.mainSize}`}</span>
            <em>
              {activeProgress.isGenerating
                ? `并行生成中 ${activeProgress.completed}/${activeProgress.total}`
                : `已加载 ${visibleItems.length}/${visibleModules.length} 张`}
            </em>
          </div>

          {activeImageGroup !== "detail" ? (
            <div className="mainImagePreview">
              {visibleModules.length > 0 ? (
                <div className="mainImageGrid">
                  {visibleModules.map((module, index) => {
                    const url = generatedByModule.get(module.id);
                    const versions = imageVersions[module.id] ?? [];
                    const isCurrent = (activeProgress.runningModuleIds ?? []).includes(module.id);
                    return (
                      <article className="mainImageCard" key={module.id}>
                        <div className="mainImageFrame">
                          {url ? (
                            <img src={url} alt={`${module.name}生成图`} loading={index > 1 ? "lazy" : "eager"} />
                          ) : (
                            <div className="emptyState mainImageEmpty">
                              <FileImage size={28} />
                              <p>{isCurrent ? "生成中..." : "待生成"}</p>
                            </div>
                          )}
                        </div>
                        <footer>
                          <b>{module.name}</b>
                          <span className="previewCardActions">
                            <button
                              className="inlineActionButton"
                              disabled={activeProgress.isGenerating}
                              onClick={() => onGenerateModule(activeImageGroup, module.id)}
                              type="button"
                            >
                              {isCurrent ? "生成中" : url ? "重新生成" : "生成"}
                            </button>
                            {url ? <a href={url} download={`${String(index + 1).padStart(2, "0")}-${module.id}.png`}>下载</a> : null}
                          </span>
                        </footer>
                        {versions.length > 0 ? (
                          <div className="versionSwitcher">
                            {versions.map((version) => (
                              <button
                                className={selectedVersionIds[module.id] === version.id ? "active" : ""}
                                key={version.id}
                                onClick={() => onSelectVersion(module.id, version.id)}
                                type="button"
                              >
                                {version.label}
                              </button>
                            ))}
                          </div>
                        ) : null}
                        {url ? (
                          <div className="editPromptRow">
                            <input
                              value={editDrafts[module.id] ?? ""}
                              placeholder="输入微调指令，例如：文字放大 30%"
                              onChange={(event) => setEditDrafts((current) => ({ ...current, [module.id]: event.target.value }))}
                            />
                            <button
                              className="inlineActionButton strong"
                              onClick={() => onEditImage(module.id, url, editDrafts[module.id] ?? "")}
                              type="button"
                            >
                              微调
                            </button>
                          </div>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <div className="emptyState previewEmpty">
                  <FileImage size={34} />
                  <h3>暂无{groupCopy[activeImageGroup].title}</h3>
                  <p>{groupCopy[activeImageGroup].empty}</p>
                </div>
              )}
            </div>
          ) : (
            <div className="longPreview">
              {groupedItems.detail.length > 0 ? (
                <div className="longImage">
                  {groupedItems.detail.map((item, index) => (
                    <section className="longImageSection" key={item.module.id} aria-label={`${item.module.name}生成图`}>
                      <img src={item.url} alt={`${item.module.name}生成图`} loading={index > 1 ? "lazy" : "eager"} />
                      <div className="longImageControls">
                        <b>{item.module.name}</b>
                        <span className="previewCardActions">
                          {(imageVersions[item.module.id] ?? []).map((version) => (
                            <button
                              className={selectedVersionIds[item.module.id] === version.id ? "versionPill active" : "versionPill"}
                              key={version.id}
                              onClick={() => onSelectVersion(item.module.id, version.id)}
                              type="button"
                            >
                              {version.label}
                            </button>
                          ))}
                          <button className="inlineActionButton" onClick={() => onGenerateModule(activeImageGroup, item.module.id)} type="button">
                            再生成一版
                          </button>
                        </span>
                        <div className="editPromptRow">
                          <input
                            value={editDrafts[item.module.id] ?? ""}
                            placeholder="输入微调指令"
                            onChange={(event) => setEditDrafts((current) => ({ ...current, [item.module.id]: event.target.value }))}
                          />
                          <button
                            className="inlineActionButton strong"
                            onClick={() => onEditImage(item.module.id, item.url, editDrafts[item.module.id] ?? "")}
                            type="button"
                          >
                            微调
                          </button>
                        </div>
                      </div>
                    </section>
                  ))}
                </div>
              ) : (
                <div className="emptyState previewEmpty">
                  <FileImage size={34} />
                  <h3>暂无详情图生成结果</h3>
                  <p>{groupCopy.detail.empty}</p>
                </div>
              )}
            </div>
          )}
        </section>

        <aside className="panel sidePanel">
          <div className="sectionTitle compact">
            <span>
              <FileImage size={20} />
            </span>
            <div>
              <h2>{groupCopy[activeImageGroup].directory}</h2>
            </div>
          </div>
          <div className="directoryList">
            {visibleModules.map((module, index) => {
              const moduleUrl = generatedByModule.get(module.id);
              const isCurrent = (activeProgress.runningModuleIds ?? []).includes(module.id);
              return (
                <div key={module.id}>
                  <span>{index + 1}</span>
                  <b>{module.name}</b>
                  <span className="directoryActions">
                    <button
                      className="inlineActionButton"
                      disabled={activeProgress.isGenerating}
                      onClick={() => onGenerateModule(activeImageGroup, module.id)}
                      type="button"
                    >
                      {isCurrent ? "生成中" : moduleUrl ? "重新生成" : "生成"}
                    </button>
                    {moduleUrl ? (
                      <a href={moduleUrl} download={`${String(index + 1).padStart(2, "0")}-${module.id}.png`}>
                        下载
                      </a>
                    ) : null}
                  </span>
                </div>
              );
            })}
          </div>
          <div className="exportActions">
            {activeImageGroup === "detail" ? (
              <>
                <button className="primaryButton" onClick={handleDownloadLongJpg} disabled={groupedItems.detail.length === 0 || isComposing}>
                  <Download size={20} />
                  {isComposing ? composeStatus || "正在合成 JPG" : groupedItems.detail.length ? `合成并下载 ${groupedItems.detail.length} 张详情图为 JPG 长图` : "暂无详情长图可导出"}
                </button>
                <a className="ghostButton" href={manifestHref} download="split-images-manifest.json">
                  <Download size={20} />
                  导出 {groupedItems.detail.length} 张详情分图清单
                </a>
                {composeStatus && !composeError ? <p className="composeStatus">{composeStatus}</p> : null}
                {composeError ? <p className="composeError">{composeError}</p> : null}
              </>
            ) : (
              <button className="primaryButton" onClick={handleDownloadVisibleBatch} disabled={visibleItems.length === 0} type="button">
                <Download size={20} />
                {visibleItems.length ? `批量下载 ${visibleItems.length} 张${batchDownloadLabel}` : "暂无可批量下载图片"}
              </button>
            )}
          </div>
        </aside>
      </div>

      <footer className="bottomActions">
        <button className="ghostButton" onClick={onBack}>
          上一步
        </button>
      </footer>
    </>
  );
}
