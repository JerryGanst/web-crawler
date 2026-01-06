export const MOCK_COMMODITIES = [
    {
        name: "Gold",
        chinese_name: "黄金",
        price: 612.50,
        change: 2.80,
        change_percent: 0.46,
        source: "Shanghai Gold Exchange",
        url: "https://www.sge.com.cn/data/Gold",
        symbol: "Au99.99",
        unit: "g"
    },
    {
        name: "Silver",
        chinese_name: "白银",
        price: 7.85,
        change: -0.04,
        change_percent: -0.51,
        source: "Shanghai Gold Exchange",
        url: "https://www.sge.com.cn/data/Silver",
        symbol: "Ag(T+D)",
        unit: "kg"
    },
    {
        name: "Copper",
        chinese_name: "铜",
        price: 74200,
        change: 450,
        change_percent: 0.61,
        source: "Shanghai Futures Exchange",
        url: "https://www.shfe.com.cn/products/Copper",
        symbol: "CU2401",
        unit: "ton"
    },
    {
        name: "Crude Oil",
        chinese_name: "原油",
        price: 512.4,
        change: -8.5,
        change_percent: -1.63,
        source: "Shanghai International Energy Exchange",
        url: "https://www.ine.cn/products/CrudeOil",
        symbol: "SC2402",
        unit: "barrel"
    }
];

export const MOCK_CONFIG = {
    target_urls: [
        "https://example.com/market/gold",
        "https://example.com/market/silver",
        "https://finance.mock.com/commodities"
    ]
};

export const MOCK_NEWS = [
    { id: 1, title: "Global Gold Demand Surges in Q3", time: "10 mins ago", source: "Financial Times" },
    { id: 2, title: "Oil Prices Stabilize After Volatile Week", time: "1 hour ago", source: "Bloomberg" },
    { id: 3, title: "Copper Supply Chain Disruptions Expected", time: "2 hours ago", source: "Reuters" },
    { id: 4, title: "Silver Futures Hit 3-Month High", time: "4 hours ago", source: "MarketWatch" },
    { id: 5, title: "Central Banks Continue Gold Accumulation", time: "5 hours ago", source: "CNBC" }
];

export const MOCK_AI_ANALYSIS = `
**Market Sentiment Analysis:**

The commodities market is currently exhibiting a **bullish** trend for precious metals, driven by global economic uncertainty and increased central bank buying. 

*   **Gold:** Strong support at 450. Upside potential remains high as inflation concerns persist.
*   **Silver:** Following Gold's lead but with higher volatility. Watch for resistance at 33.
*   **Copper:** Industrial demand is steady, but supply chain constraints may push prices higher in the short term.
*   **Oil:** Currently consolidating. Geopolitical factors are the primary driver of volatility.

**Recommendation:** Maintain long positions in Gold and Silver. Monitor Copper for breakout signals.
`;
