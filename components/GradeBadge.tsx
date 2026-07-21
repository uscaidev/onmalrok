import type { LinkGrade } from "@/lib/types";
import styles from "./GradeBadge.module.css";

// §5.2 색·문구 고정. 연결 UI에 이 컴포넌트 없이 연결 표시 금지 (§9-2)
const GRADE: Record<LinkGrade, { label: string; className: string }> = {
  explicit: { label: "✓ 발언 명시", className: styles.explicit },
  topic: { label: "# 주제 연결", className: styles.topic },
  ai_inferred: { label: "≈ AI 추정", className: styles.aiInferred },
};

export default function GradeBadge({ grade }: { grade: LinkGrade }) {
  const g = GRADE[grade];
  return <span className={`${styles.badge} ${g.className}`}>{g.label}</span>;
}
