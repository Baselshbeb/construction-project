"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  ReactNode,
} from "react";

import en from "../translations/en.json";
import tr from "../translations/tr.json";
import ar from "../translations/ar.json";

export type Language = "en" | "tr" | "ar";

const translations: Record<Language, Record<string, string>> = { en, tr, ar };

const RTL_LANGUAGES: Language[] = ["ar"];

interface LanguageContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: (key: string) => string;
  dir: "ltr" | "rtl";
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = "metraj-language";

function detectLanguage(): Language {
  // 1. Check localStorage
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem(STORAGE_KEY) as Language | null;
    if (stored && stored in translations) return stored;
  }

  // 2. Check browser language
  if (typeof navigator !== "undefined") {
    const browserLang = navigator.language.split("-")[0];
    if (browserLang === "tr") return "tr";
    if (browserLang === "ar") return "ar";
  }

  return "en";
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>("en");

  useEffect(() => {
    setLanguageState(detectLanguage());
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    localStorage.setItem(STORAGE_KEY, lang);
  }, []);

  const t = useCallback(
    (key: string): string => {
      return translations[language]?.[key] ?? translations.en[key] ?? key;
    },
    [language]
  );

  const dir = RTL_LANGUAGES.includes(language) ? "rtl" : "ltr";

  // Update <html> lang and dir attributes
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = dir;
  }, [language, dir]);

  return (
    <LanguageContext.Provider value={{ language, setLanguage, t, dir }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useTranslation must be used within LanguageProvider");
  return ctx;
}

export function LanguageSwitcher() {
  const { language, setLanguage } = useTranslation();

  const labels: Record<Language, string> = {
    en: "EN",
    tr: "TR",
    ar: "AR",
  };

  return (
    <div className="flex gap-1">
      {(Object.keys(labels) as Language[]).map((lang) => (
        <button
          key={lang}
          onClick={() => setLanguage(lang)}
          className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors ${
            language === lang
              ? "bg-primary text-white"
              : "bg-gray-100 text-gray-600 hover:bg-gray-200"
          }`}
        >
          {labels[lang]}
        </button>
      ))}
    </div>
  );
}
