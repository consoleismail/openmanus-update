import asyncio
from app.tool.search.google_search import GoogleSearchEngine
from app.tool.search.duckduckgo_search import DuckDuckGoSearchEngine
from app.tool.search.baidu_search import BaiduSearchEngine
from app.tool.search.bing_search import BingSearchEngine

async def test_engines():
    engines = {
        "google": GoogleSearchEngine(),
        "duckduckgo": DuckDuckGoSearchEngine(),
        "baidu": BaiduSearchEngine(),
        "bing": BingSearchEngine(),
    }
    
    query = "collect email list for sell domain executeshellcom.com"
    num_results = 5
    search_params = {"lang": "en", "country": "us"}
    
    for name, engine in engines.items():
        print(f"Testing {name}...")
        try:
            results = await asyncio.get_event_loop().run_in_executor(
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
            print(f"  {name} success: {len(results)} results")
        except Exception as e:
            print(f"  {name} failed: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_engines())
