import asyncio
from typing import Dict, Any, List
from tenacity import retry, stop_after_attempt, wait_exponential
from app.tool.search.base import SearchItem, WebSearchEngine
from app.tool.search.bing_search import BingSearchEngine

class MockWebSearch:
    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10)
    )
    async def _perform_search_with_engine(
        self,
        engine: WebSearchEngine,
        query: str,
        num_results: int,
        search_params: Dict[str, Any],
    ) -> List[SearchItem]:
        print(f"Executing search for {query}...")
        return await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: list(
                engine.perform_search(
                    query,
                    num_results=num_results,
                    lang=search_params.get("lang"),
                    country=search_params.get("country"),
                )
            ),
        )

async def main():
    searcher = MockWebSearch()
    engine = BingSearchEngine()
    query = "test"
    num_results = 5
    search_params = {"lang": "en", "country": "us"}
    
    try:
        results = await searcher._perform_search_with_engine(
            engine, query, num_results, search_params
        )
        print(f"Success: {len(results)} results")
    except Exception as e:
        print(f"Failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
