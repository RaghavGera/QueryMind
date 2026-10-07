import Universe from "../components/universe/Universe";
import ChapterRail from "../components/landing/ChapterRail";
import HeroChapter from "../components/landing/chapters/HeroChapter";
import QuestionChapter from "../components/landing/chapters/QuestionChapter";
import SchemaChapter from "../components/landing/chapters/SchemaChapter";
import AmbiguityChapter from "../components/landing/chapters/AmbiguityChapter";
import SqlChapter from "../components/landing/chapters/SqlChapter";
import AnswerChapter from "../components/landing/chapters/AnswerChapter";
import SafetyChapter from "../components/landing/chapters/SafetyChapter";
import ConsoleChapter from "../components/landing/chapters/ConsoleChapter";
import LaunchChapter from "../components/landing/chapters/LaunchChapter";

/**
 * "Neural Observatory": one continuous camera flight. A fixed WebGL universe
 * sits behind pinned, scroll-scrubbed chapters; each chapter is one stage of
 * the real pipeline, with real wording, SQL and numbers from the demo DB.
 */
export default function Landing() {
  return (
    <>
      <Universe />
      <ChapterRail />
      <HeroChapter />
      <QuestionChapter />
      <SchemaChapter />
      <AmbiguityChapter />
      <SqlChapter />
      <AnswerChapter />
      <SafetyChapter />
      <ConsoleChapter />
      <LaunchChapter />
    </>
  );
}
