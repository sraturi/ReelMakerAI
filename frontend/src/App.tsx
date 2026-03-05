import { AppShell } from "./components/layout/AppShell";
import { UploadPage } from "./components/upload/UploadPage";
import { PromptPage } from "./components/prompt/PromptPage";
import { EditorPage } from "./components/editor/EditorPage";
import { RenderPage } from "./components/render/RenderPage";
import { VideoPreview } from "./components/render/VideoPreview";
import { LoadingOverlay } from "./components/shared/LoadingOverlay";
import { useUIStore } from "./store/useUIStore";

export default function App() {
  const step = useUIStore((s) => s.step);

  return (
    <AppShell>
      {step === "upload" && <UploadPage />}
      {step === "analyze" && <UploadPage />}
      {step === "prompt" && <PromptPage />}
      {step === "edit" && <EditorPage />}
      {step === "render" && <RenderPage />}
      {step === "preview" && <VideoPreview />}
      <LoadingOverlay />
    </AppShell>
  );
}
