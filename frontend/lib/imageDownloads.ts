export function isDataImageUrl(url: string) {
  return /^data:image\//i.test(url);
}

export function isDirectDownloadUrl(url: string) {
  return /^https?:\/\//i.test(url);
}

function dataImageUrlToBlob(url: string) {
  const separatorIndex = url.indexOf(",");
  if (separatorIndex < 0) throw new Error("无效的 base64 图片数据");

  const header = url.slice(0, separatorIndex);
  const payload = url.slice(separatorIndex + 1);
  const mimeType = header.match(/^data:([^;,]+)/i)?.[1] ?? "application/octet-stream";
  const binary = header.includes(";base64") ? atob(payload) : decodeURIComponent(payload);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mimeType });
}

export async function fetchImageBlob(url: string, proxyDownload: (url: string) => Promise<Blob>) {
  if (isDataImageUrl(url)) {
    return dataImageUrlToBlob(url);
  }

  if (isDirectDownloadUrl(url)) {
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`Image fetch failed: ${response.status}`);
      return await response.blob();
    } catch {
      return proxyDownload(url);
    }
  }

  return proxyDownload(url);
}
