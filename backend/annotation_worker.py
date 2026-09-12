"""Proses worker MinerU yang berdiri sendiri, terpisah dari proses Uvicorn."""
import paths

paths.setup()

import db
import jobs

if __name__ == "__main__":
    db.init_db()
    print("[INFO] worker MinerU jalan, menunggu job di antrean...")
    jobs.run_worker_forever()
