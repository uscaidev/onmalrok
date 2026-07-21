import styles from "./AiLabel.module.css";

// AI 산출물엔 라벨 (철학 6). 누락 금지 (§9-4)
const LABEL = {
  summary: "AI 요약",
  speaker: "화자 AI 추정",
  link: "≈ AI 추정",
} as const;

export default function AiLabel({ type }: { type: keyof typeof LABEL }) {
  return <span className={styles.label}>{LABEL[type]}</span>;
}
