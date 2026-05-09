"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock, Search, Trash2, RotateCcw, X, Image as ImageIcon } from "lucide-react";
import { deleteHistoryRecord, fetchHistoryDetail, fetchHistoryList, type HistoryMeta } from "@/lib/historyApi";
import type { PersistedProjectState } from "@/lib/types";

function relativeTime(isoDate: string): string {
  const ms = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return new Date(isoDate).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
}

function formatDate(isoDate: string): string {
  const date = new Date(isoDate);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  });
}

export function HistoryDrawer({
  open,
  onClose,
  onRestoreCopy
}: {
  open: boolean;
  onClose: () => void;
  onRestoreCopy: (state: PersistedProjectState, historyId?: string) => void;
}) {
  const [items, setItems] = useState<HistoryMeta[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const loadItems = useCallback(async () => {
    setIsLoading(true);
    const data = await fetchHistoryList(50);
    setItems(data);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    if (open) {
      void loadItems();
    }
  }, [open, loadItems]);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && open) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  async function handleRestore(id: string) {
    if (restoringId) return;
    setRestoringId(id);
    const detail = await fetchHistoryDetail(id);
    setRestoringId(null);
    if (detail?.state) {
      onRestoreCopy(detail.state, detail.id);
      onClose();
    }
  }

  async function handleDelete(id: string) {
    if (deletingId) return;
    setDeletingId(id);
    const deleted = await deleteHistoryRecord(id);
    setDeletingId(null);
    if (deleted) {
      setItems((current) => current.filter((item) => item.id !== id));
    }
  }

  const filteredItems = searchQuery.trim()
    ? items.filter(
        (item) =>
          item.product_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
          item.style_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : items;

  return (
    <>
      <div
        className={`historyOverlay ${open ? "open" : ""}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside className={`historyDrawer ${open ? "open" : ""}`} aria-label="历史记录">
        <header className="historyDrawerHeader">
          <div className="historyDrawerTitle">
            <Clock size={20} />
            <h2>历史记录</h2>
          </div>
          <button className="historyCloseButton" onClick={onClose} type="button" aria-label="关闭">
            <X size={20} />
          </button>
        </header>

        <div className="historySearchBar">
          <Search size={16} />
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder="搜索产品名称..."
            type="search"
          />
        </div>

        <div className="historyList">
          {isLoading ? (
            <div className="historyEmptyState">
              <p>正在加载...</p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="historyEmptyState">
              <Clock size={32} />
              <p>{searchQuery ? "没有找到匹配的记录" : "暂无历史记录"}</p>
              <span>{searchQuery ? "试试其他关键词" : "生成图片后点击保存，会出现在这里"}</span>
            </div>
          ) : (
            filteredItems.map((item) => (
              <article className="historyCard" key={item.id}>
                <div className="historyCardTop">
                  <div className="historyCardThumbnail">
                    {item.thumbnail ? (
                      <img src={item.thumbnail} alt="" loading="lazy" />
                    ) : (
                      <div className="historyCardPlaceholder">
                        <ImageIcon size={22} />
                      </div>
                    )}
                  </div>
                  <div className="historyCardInfo">
                    <b className="historyCardName">{item.product_name || "未命名项目"}</b>
                    <div className="historyCardMeta">
                      <span className="historyStyleDot" style={{ background: getStyleColor(item.style_id) }} />
                      <span>{item.style_name || item.style_id}</span>
                      <span>·</span>
                      <span>{item.category || "未分类"}</span>
                    </div>
                    <div className="historyCardMeta">
                      <span>{item.image_count} 张图片</span>
                      <span>·</span>
                      <time title={item.created_at}>{relativeTime(item.created_at)}</time>
                    </div>
                  </div>
                </div>
                <div className="historyCardActions">
                  <button
                    className="historyRestoreButton"
                    onClick={() => handleRestore(item.id)}
                    disabled={restoringId === item.id}
                    type="button"
                  >
                    <RotateCcw size={14} />
                    {restoringId === item.id ? "载入中..." : "载入副本"}
                  </button>
                  <button
                    className="historyDeleteButton"
                    onClick={() => handleDelete(item.id)}
                    disabled={deletingId === item.id}
                    type="button"
                  >
                    <Trash2 size={14} />
                    {deletingId === item.id ? "删除中" : "删除"}
                  </button>
                  <span className="historyCardDate">{formatDate(item.created_at)}</span>
                </div>
              </article>
            ))
          )}
        </div>
      </aside>
    </>
  );
}

function getStyleColor(styleId: string): string {
  const colorMap: Record<string, string> = {
    green_repair: "#2fa657",
    blue_hydra: "#3b82f6",
    gold_antiage: "#d4a253",
    ai_custom: "#7c3aed"
  };
  return colorMap[styleId] ?? "#9ca3af";
}
