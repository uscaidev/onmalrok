"use client";

import { useState } from "react";
import styles from "./QuoteText.module.css";

// 발언 인용 전용 명조 렌더 (§5.3). corrected=true면 ⓘ로 자동자막 원문(text_raw) 열람.
// AI 생성 텍스트에는 이 컴포넌트를 쓰지 않는다 (§9-4).
export default function QuoteText({
  text,
  raw,
  corrected,
  highlight,
}: {
  text: string;
  raw: string;
  corrected: boolean;
  highlight?: string;
}) {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <span className={styles.quote}>
      {highlight ? highlightText(text, highlight) : text}
      {corrected && (
        <>
          {" "}
          <button
            type="button"
            className={styles.info}
            aria-label="자동자막 원문 보기"
            aria-expanded={showRaw}
            onClick={() => setShowRaw((v) => !v)}
          >
            ⓘ
          </button>
          {showRaw && (
            <span className={styles.rawTip}>
              <span className={styles.rawLabel}>자동자막 원문</span>
              {raw}
            </span>
          )}
        </>
      )}
    </span>
  );
}

function highlightText(text: string, query: string) {
  const q = query.trim();
  if (!q) return text;
  const parts: (string | JSX.Element)[] = [];
  let rest = text;
  let key = 0;
  while (rest.length > 0) {
    const idx = rest.toLowerCase().indexOf(q.toLowerCase());
    if (idx === -1) {
      parts.push(rest);
      break;
    }
    if (idx > 0) parts.push(rest.slice(0, idx));
    parts.push(<mark key={key++}>{rest.slice(idx, idx + q.length)}</mark>);
    rest = rest.slice(idx + q.length);
  }
  return parts;
}
