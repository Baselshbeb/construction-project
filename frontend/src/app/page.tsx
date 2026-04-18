"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { useTranslation, LanguageSwitcher } from "../context/LanguageContext";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type AppState = "upload" | "processing" | "results" | "error";

interface ProgressData {
  step: string;
  current: number;
  total: number;
  percent: number;
}

interface ProjectResult {
  building_info: Record<string, unknown> | null;
  classified_elements: Record<string, number>;
  material_count: number;
  materials: Material[];
  boq_data: BOQData | null;
  boq_file_paths: Record<string, string>;
  validation_report: ValidationReport | null;
  warnings: string[];
  errors: string[];
  element_count: number;
}

interface Material {
  description: string;
  unit: string;
  quantity: number;
  total_quantity: number;
  waste_factor: number;
  category: string;
}

interface ConfidenceData {
  level: "high" | "medium" | "low";
  score: number;
  factors: string[];
  review_needed: boolean;
}

interface ConfidenceSummary {
  high_count: number;
  medium_count: number;
  low_count: number;
  total_items: number;
  review_needed_count: number;
  overall_score: number;
  overall_level: string;
}

interface BOQData {
  project_name: string;
  building_name: string | null;
  sections: BOQSection[];
  total_line_items: number;
  total_sections: number;
  confidence_summary?: ConfidenceSummary;
}

interface BOQSection {
  section_no: number;
  title: string;
  items: BOQItem[];
}

interface BOQItem {
  item_no: string;
  description: string;
  unit: string;
  quantity: number;
  rate: number | null;
  amount: number | null;
  confidence?: ConfidenceData;
  base_quantity?: number;
  waste_factor?: number;
}

interface ValidationReport {
  status: string;
  score: string;
  summary: Record<string, number>;
}

const PIPELINE_STEP_KEYS = [
  "pipeline.parsing",
  "pipeline.classification",
  "pipeline.calculation",
  "pipeline.mapping",
  "pipeline.generation",
  "pipeline.validation",
] as const;

export default function Home() {
  const { t, language } = useTranslation();
  const [appState, setAppState] = useState<AppState>("upload");
  const [projectId, setProjectId] = useState<string>("");
  const [filename, setFilename] = useState<string>("");
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [result, setResult] = useState<ProjectResult | null>(null);
  const [error, setError] = useState<string>("");
  const [dragActive, setDragActive] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [reportLanguage, setReportLanguage] = useState(language);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // Restore session on mount (survives page refresh)
  useEffect(() => {
    try {
      const saved = sessionStorage.getItem("metraj-session");
      if (saved) {
        const session = JSON.parse(saved);
        if (session.projectId && session.appState === "processing") {
          setProjectId(session.projectId);
          setFilename(session.filename || "");
          setReportLanguage(session.reportLanguage || "en");
          setAppState("processing");
          setProgress({ step: "Reconnecting...", current: 0, total: 6, percent: 0 });
          connectWebSocket(session.projectId);
        }
      }
    } catch {
      // Ignore corrupted session data
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Clean up WebSocket on unmount
  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const connectWebSocket = useCallback((pid: string, retries = 0) => {
    const MAX_RETRIES = 5;
    const wsUrl = API_URL.replace("http", "ws");
    const ws = new WebSocket(`${wsUrl}/ws/${pid}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      if (data.type === "progress" || data.type === "status") {
        setProgress({
          step: data.step || data.status || "",
          current: data.current || 0,
          total: data.total || 6,
          percent: data.percent || 0,
        });
      } else if (data.type === "complete") {
        setResult(data.result);
        setAppState("results");
        // Clear saved session on completion
        sessionStorage.removeItem("metraj-session");
        ws.close();
      } else if (data.type === "error") {
        setError(data.message);
        setAppState("error");
        sessionStorage.removeItem("metraj-session");
        ws.close();
      }
    };

    ws.onclose = (event) => {
      // Only reconnect if we're still processing (not completed/error)
      if (retries < MAX_RETRIES && appState === "processing" && !event.wasClean) {
        const delay = Math.min(1000 * Math.pow(2, retries), 10000);
        console.log(`WebSocket closed, reconnecting in ${delay}ms (attempt ${retries + 1}/${MAX_RETRIES})`);
        setTimeout(() => connectWebSocket(pid, retries + 1), delay);
      }
    };

    ws.onerror = () => {
      // onclose will handle reconnection; only show error if all retries exhausted
      if (retries >= MAX_RETRIES) {
        setError(t("error.wsConnection"));
        setAppState("error");
        sessionStorage.removeItem("metraj-session");
      }
    };
  }, [t, appState]);

  const uploadFile = useCallback(
    async (file: File) => {
      if (!file.name.toLowerCase().endsWith(".ifc")) {
        setError(t("upload.invalidFile"));
        setAppState("error");
        return;
      }

      setFilename(file.name);
      setAppState("processing");
      setProgress({ step: t("processing.uploading"), current: 0, total: 6, percent: 0 });

      try {
        const formData = new FormData();
        formData.append("file", file);

        const response = await fetch(`${API_URL}/api/projects/upload?language=${language}`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const err = await response.json();
          throw new Error(err.detail || "Upload failed");
        }

        const data = await response.json();
        setProjectId(data.project_id);
        setReportLanguage(language);

        // Save session so it survives page refresh
        sessionStorage.setItem("metraj-session", JSON.stringify({
          projectId: data.project_id,
          filename: file.name,
          reportLanguage: language,
          appState: "processing",
        }));

        connectWebSocket(data.project_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        setAppState("error");
      }
    },
    [connectWebSocket, t, language]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragActive(false);
      const file = e.dataTransfer.files[0];
      if (file) uploadFile(file);
    },
    [uploadFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) uploadFile(file);
    },
    [uploadFile]
  );

  const resetApp = () => {
    setAppState("upload");
    setProjectId("");
    setFilename("");
    setProgress(null);
    setResult(null);
    setError("");
  };

  const downloadReport = (format: string) => {
    window.open(`${API_URL}/api/projects/${projectId}/download/${format}`, "_blank");
  };

  const regenerateReport = useCallback(async () => {
    if (!projectId || regenerating) return;

    setRegenerating(true);
    setAppState("processing");
    setProgress({ step: t("processing.uploading"), current: 0, total: 6, percent: 0 });
    setResult(null);

    try {
      const response = await fetch(
        `${API_URL}/api/projects/${projectId}/reprocess?language=${language}`,
        { method: "POST" }
      );

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || "Reprocess failed");
      }

      setReportLanguage(language);
      connectWebSocket(projectId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reprocess failed");
      setAppState("error");
    } finally {
      setRegenerating(false);
    }
  }, [projectId, regenerating, language, connectWebSocket, t]);

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary">{t("app.title")}</h1>
            <p className="text-sm text-gray-500">
              {t("app.subtitle")}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <LanguageSwitcher />
            {appState !== "upload" && (
              <button
                onClick={resetApp}
                className="text-sm px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors"
              >
                {t("nav.newProject")}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-6 py-8">
        {/* Upload State */}
        {appState === "upload" && (
          <div className="max-w-2xl mx-auto">
            <div className="text-center mb-8">
              <h2 className="text-3xl font-bold text-foreground mb-2">
                {t("upload.title")}
              </h2>
              <p className="text-gray-500">
                {t("upload.description")}
              </p>
            </div>

            <div
              className={`border-2 border-dashed rounded-2xl p-16 text-center transition-all cursor-pointer
                ${
                  dragActive
                    ? "border-primary bg-primary-light/30 scale-[1.02]"
                    : "border-gray-300 hover:border-primary hover:bg-gray-50"
                }`}
              onDragOver={(e) => {
                e.preventDefault();
                setDragActive(true);
              }}
              onDragLeave={() => setDragActive(false)}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="text-6xl mb-4">
                {dragActive ? "+" : ""}
              </div>
              <p className="text-lg font-medium text-foreground mb-1">
                {dragActive
                  ? t("upload.dropActive")
                  : t("upload.dropzone")}
              </p>
              <p className="text-sm text-gray-400 mb-4">{t("upload.browse")}</p>
              <span className="inline-block px-4 py-2 bg-primary text-white rounded-lg text-sm font-medium">
                {t("upload.selectFile")}
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".ifc"
                onChange={handleFileSelect}
                className="hidden"
              />
            </div>

            <div className="mt-8 grid grid-cols-3 gap-4 text-center text-sm">
              <div className="p-4 rounded-xl bg-white border border-gray-100">
                <div className="text-2xl font-bold text-primary mb-1">1</div>
                <p className="font-medium">{t("steps.upload")}</p>
                <p className="text-gray-400">{t("steps.uploadDesc")}</p>
              </div>
              <div className="p-4 rounded-xl bg-white border border-gray-100">
                <div className="text-2xl font-bold text-primary mb-1">2</div>
                <p className="font-medium">{t("steps.analyze")}</p>
                <p className="text-gray-400">{t("steps.analyzeDesc")}</p>
              </div>
              <div className="p-4 rounded-xl bg-white border border-gray-100">
                <div className="text-2xl font-bold text-primary mb-1">3</div>
                <p className="font-medium">{t("steps.getBOQ")}</p>
                <p className="text-gray-400">{t("steps.getBOQDesc")}</p>
              </div>
            </div>
          </div>
        )}

        {/* Processing State */}
        {appState === "processing" && progress && (
          <div className="max-w-lg mx-auto text-center">
            <h2 className="text-2xl font-bold mb-2">
              {t("processing.title").replace("{filename}", filename)}
            </h2>
            <p className="text-gray-500 mb-8">
              {t("processing.subtitle")}
            </p>

            {/* Progress bar */}
            <div className="mb-6">
              <div className="flex justify-between text-sm mb-2">
                <span className="font-medium text-primary">{progress.step}</span>
                <span className="text-gray-400">
                  {progress.current}/{progress.total}
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all duration-500 ease-out"
                  style={{
                    width: `${Math.max(progress.percent, 5)}%`,
                    backgroundColor: "var(--primary)",
                  }}
                />
              </div>
            </div>

            {/* Pipeline steps */}
            <div className="text-left space-y-3">
              {PIPELINE_STEP_KEYS.map((key, i) => {
                const step = t(key);
                const stepNum = i + 1;
                const isDone = stepNum < progress.current;
                const isCurrent = stepNum === progress.current;

                return (
                  <div
                    key={key}
                    className={`flex items-center gap-3 p-3 rounded-lg transition-all ${
                      isCurrent
                        ? "bg-primary-light/40 border border-primary/20"
                        : isDone
                        ? "bg-green-50"
                        : "bg-gray-50"
                    }`}
                  >
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center text-sm font-medium ${
                        isDone
                          ? "bg-green-500 text-white"
                          : isCurrent
                          ? "bg-primary text-white"
                          : "bg-gray-200 text-gray-500"
                      }`}
                    >
                      {isDone ? "\u2713" : stepNum}
                    </div>
                    <span
                      className={`${
                        isCurrent
                          ? "font-medium text-primary"
                          : isDone
                          ? "text-green-700"
                          : "text-gray-400"
                      }`}
                    >
                      {step}
                    </span>
                    {isCurrent && (
                      <div className="ms-auto">
                        <div className="w-5 h-5 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Results State */}
        {appState === "results" && result && (
          <div>
            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <SummaryCard
                label={t("results.elementsParsed")}
                value={result.element_count}
              />
              <SummaryCard
                label={t("results.materialsFound")}
                value={result.material_count}
              />
              <SummaryCard
                label={t("results.boqSections")}
                value={result.boq_data?.total_sections || 0}
              />
              <SummaryCard
                label={t("results.validation")}
                value={result.validation_report?.status || "N/A"}
                isText
              />
            </div>

            {/* Confidence summary */}
            {result.boq_data?.confidence_summary && (
              <div className="flex gap-3 mb-6 text-sm">
                <span className="px-3 py-1 rounded-full bg-green-100 text-green-800 font-medium">
                  HIGH: {result.boq_data.confidence_summary.high_count}
                </span>
                <span className="px-3 py-1 rounded-full bg-yellow-100 text-yellow-800 font-medium">
                  MEDIUM: {result.boq_data.confidence_summary.medium_count}
                </span>
                <span className="px-3 py-1 rounded-full bg-red-100 text-red-800 font-medium">
                  LOW: {result.boq_data.confidence_summary.low_count}
                </span>
                <span className="px-3 py-1 rounded-full bg-gray-100 text-gray-600">
                  Overall: {Math.round((result.boq_data.confidence_summary.overall_score || 0) * 100)}%
                </span>
                {result.boq_data.confidence_summary.review_needed_count > 0 && (
                  <span className="px-3 py-1 rounded-full bg-orange-100 text-orange-700 font-medium">
                    {result.boq_data.confidence_summary.review_needed_count} items need review
                  </span>
                )}
              </div>
            )}

            {/* Download buttons */}
            <div className="flex flex-wrap gap-3 mb-8">
              <button
                onClick={() => downloadReport("xlsx")}
                className="px-5 py-2.5 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors"
              >
                {t("download.excel")}
              </button>
              <button
                onClick={() => downloadReport("csv")}
                className="px-5 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
              >
                {t("download.csv")}
              </button>
              <button
                onClick={() => downloadReport("json")}
                className="px-5 py-2.5 bg-gray-600 text-white rounded-lg font-medium hover:bg-gray-700 transition-colors"
              >
                {t("download.json")}
              </button>

              {language !== reportLanguage && (
                <button
                  onClick={regenerateReport}
                  disabled={regenerating}
                  className="px-5 py-2.5 bg-orange-500 text-white rounded-lg font-medium hover:bg-orange-600 transition-colors disabled:opacity-50 ms-auto"
                >
                  {regenerating
                    ? t("download.regenerating")
                    : t("download.regenerate").replace(
                        "{lang}",
                        { en: "English", tr: "Turkce", ar: "العربية" }[language]
                      )}
                </button>
              )}
            </div>

            {/* BOQ Table */}
            {result.boq_data && (
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <div className="p-4 border-b border-gray-200 bg-gray-50">
                  <h3 className="text-lg font-bold text-foreground">
                    {t("boq.title")}
                  </h3>
                  <p className="text-sm text-gray-500">
                    {result.boq_data.project_name}
                    {result.boq_data.building_name &&
                      ` - ${result.boq_data.building_name}`}
                  </p>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-white" style={{ backgroundColor: "var(--primary)" }}>
                        <th className="px-4 py-3 text-start w-20">{t("boq.itemNo")}</th>
                        <th className="px-4 py-3 text-start">{t("boq.description")}</th>
                        <th className="px-4 py-3 text-center w-16">{t("boq.unit")}</th>
                        <th className="px-4 py-3 text-end w-28">{t("boq.quantity")}</th>
                        <th className="px-4 py-3 text-center w-24">Confidence</th>
                      </tr>
                    </thead>
                    <tbody>
                      {result.boq_data.sections.map((section) => (
                        <SectionRows key={section.section_no} section={section} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Validation Report */}
            {result.validation_report && (
              <div className="mt-6 bg-white rounded-xl border border-gray-200 p-4">
                <h3 className="text-lg font-bold mb-3">{t("validation.title")}</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  {result.validation_report.summary &&
                    Object.entries(result.validation_report.summary).map(
                      ([key, value]) => (
                        <div
                          key={key}
                          className="p-3 bg-gray-50 rounded-lg"
                        >
                          <p className="text-gray-500 text-xs">
                            {key.replace(/_/g, " ")}
                          </p>
                          <p className="font-bold text-lg">
                            {typeof value === "number" ? value.toFixed(2) : value}
                          </p>
                        </div>
                      )
                    )}
                </div>
              </div>
            )}

            {/* Warnings */}
            {result.warnings.length > 0 && (
              <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-xl">
                <h4 className="font-bold text-yellow-800 mb-2">
                  {t("validation.warnings").replace("{count}", String(result.warnings.length))}
                </h4>
                <ul className="text-sm text-yellow-700 space-y-1">
                  {result.warnings.map((w, i) => (
                    <li key={i}>- {w}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* Error State */}
        {appState === "error" && (
          <div className="max-w-lg mx-auto text-center">
            <div className="text-6xl mb-4">!</div>
            <h2 className="text-2xl font-bold text-danger mb-2">
              {t("error.title")}
            </h2>
            <p className="text-gray-500 mb-6">{error}</p>
            <button
              onClick={resetApp}
              className="px-6 py-2.5 bg-primary text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
            >
              {t("error.tryAgain")}
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-200 mt-16">
        <div className="max-w-6xl mx-auto px-6 py-4 text-center text-sm text-gray-400">
          {t("footer.text")}
        </div>
      </footer>
    </div>
  );
}

/* ---------- Sub-components ---------- */

function SummaryCard({
  label,
  value,
  isText = false,
}: {
  label: string;
  value: number | string;
  isText?: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4">
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <p className={`font-bold ${isText ? "text-lg" : "text-2xl"} text-foreground`}>
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
    </div>
  );
}

const CONFIDENCE_STYLES: Record<string, string> = {
  high: "bg-green-100 text-green-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-red-100 text-red-800",
};

function SectionRows({ section }: { section: BOQSection }) {
  return (
    <>
      {/* Section header */}
      <tr style={{ backgroundColor: "var(--primary-light)" }}>
        <td
          colSpan={5}
          className="px-4 py-2 font-bold"
          style={{ color: "var(--primary)" }}
        >
          {section.section_no}. {section.title}
        </td>
      </tr>
      {/* Items */}
      {section.items.map((item) => {
        const confLevel = item.confidence?.level || "medium";
        return (
          <tr key={item.item_no} className="border-b border-gray-100 hover:bg-gray-50">
            <td className="px-4 py-2 text-gray-500">{item.item_no}</td>
            <td className="px-4 py-2">{item.description}</td>
            <td className="px-4 py-2 text-center text-gray-500">{item.unit}</td>
            <td className="px-4 py-2 text-end font-mono">
              {item.quantity.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </td>
            <td className="px-4 py-2 text-center">
              <span
                className={`px-2 py-0.5 rounded-full text-xs font-medium ${CONFIDENCE_STYLES[confLevel]}`}
                title={item.confidence?.factors?.join(", ") || ""}
              >
                {confLevel.toUpperCase()}
              </span>
            </td>
          </tr>
        );
      })}
    </>
  );
}
