from taskiq import InMemoryBroker, TaskiqEvents 
from app.core.mail import send_otp_email_async
from app.core.taskiq import broker

@broker.task
async def send_otp_task(to_email: str, otp_code: str) -> None:
    await send_otp_email_async(to_email=to_email, otp_code=otp_code)