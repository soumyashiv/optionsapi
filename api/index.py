import sys
import os

# Add project root to sys.path so 'chain' module can be found
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from chain.fetcher import fetch_option_chain_compact, NSEFetchError

app = FastAPI(title="Option Chain API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/options")
async def get_options(
    symbol: str = Query("NIFTY", description="Stock or Index symbol (e.g. NIFTY)"),
    is_index: bool = Query(True, description="True for Index, False for Equity"),
    exchange: str = Query("NSE", description="NSE or BSE")
):
    try:
        data = await fetch_option_chain_compact(symbol.upper(), is_index=is_index, exchange=exchange.upper())
        return data
    except NSEFetchError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
