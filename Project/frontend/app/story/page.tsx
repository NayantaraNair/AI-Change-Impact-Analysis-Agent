import { Suspense } from "react";
import { StoryRoute } from "@/components/analysis/story-route";

export default function StoryPage() {
  return (
    <Suspense fallback={<p role="status" className="text-muted">Loading story analysis…</p>}>
      <StoryRoute />
    </Suspense>
  );
}
