from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class QuizRequestUpdate(BaseModel):
    classroom_id : int
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    max_duration_minutes: Optional[int] = Field(
        None, gt=0, description="Durasi pengerjaan dalam menit (> 0)"
    )
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_partial_schedule(self) -> "QuizRequestUpdate":
        now = datetime.now(timezone.utc)

        start = (
            self.start_time.replace(tzinfo=timezone.utc)
            if self.start_time and not self.start_time.tzinfo
            else self.start_time
        )
        end = (
            self.end_time.replace(tzinfo=timezone.utc)
            if self.end_time and not self.end_time.tzinfo
            else self.end_time
        )

        # 1. Start time must not be in the past (if provided)
        if start and start < now:
            raise ValueError("Waktu mulai (start_time) tidak boleh di masa lalu.")

        # 2. End time must be after start time (if both provided in payload)
        if start and end and end <= start:
            raise ValueError("Waktu selesai (end_time) harus lebih besar dari waktu mulai.")

        # 3. Available window check (if all three provided in payload)
        if start and end and self.max_duration_minutes:
            window_minutes = (end - start).total_seconds() / 60.0
            if window_minutes < self.max_duration_minutes:
                raise ValueError(
                    f"Rentang waktu kuis ({int(window_minutes)} menit) tidak boleh lebih pendek "
                    f"dari durasi pengerjaan kuis ({self.max_duration_minutes} menit)."
                )

        return self