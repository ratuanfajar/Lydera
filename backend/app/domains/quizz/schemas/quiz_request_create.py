from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator


class QuizChapterRequest(BaseModel):
    chapter_id: int
    hots_count: int
    lots_count: int


class QuizRequestCreate(BaseModel):
    classroom_id: int
    module_id: int
    title: str = Field(min_length=1, max_length=255)
    chapters: list[QuizChapterRequest] = Field(min_items=1)
    max_duration_minutes: int = Field(..., gt=0, description="Durasi pengerjaan dalam menit (> 0)")
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_schedule(self) -> "QuizRequestCreate":
        now = datetime.now(timezone.utc)

        start = (
            self.start_time
            if self.start_time.tzinfo
            else self.start_time.replace(tzinfo=timezone.utc)
        )
        end = (
            self.end_time
            if self.end_time.tzinfo
            else self.end_time.replace(tzinfo=timezone.utc)
        )

        # 1. Start time validation (must not be in the past)
        if start < now:
            raise ValueError("Waktu mulai (start_time) tidak boleh di masa lalu.")

        # 2. End time validation (must be strictly after start_time)
        if end <= start:
            raise ValueError("Waktu selesai (end_time) harus lebih besar dari waktu mulai.")

        # 3. Available window validation (end_time - start_time >= max_duration_minutes)
        window_minutes = (end - start).total_seconds() / 60.0
        if window_minutes < self.max_duration_minutes:
            raise ValueError(
                f"Rentang waktu kuis ({int(window_minutes)} menit) tidak boleh lebih pendek "
                f"dari durasi pengerjaan kuis ({self.max_duration_minutes} menit)."
            )

        return self

