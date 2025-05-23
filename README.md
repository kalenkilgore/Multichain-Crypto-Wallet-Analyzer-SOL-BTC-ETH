# Crypto Wallet Analyzer

A web application that analyzes cryptocurrency wallet transactions across multiple blockchains. Currently supports:
- Bitcoin (BTC)
- Ethereum (ETH)
- Solana (SOL)
- Binance Smart Chain (BNB)
- Polygon (MATIC)
- Avalanche (AVAX)
- Fantom (FTM)
- Arbitrum (ARB)
- Optimism (OP)

## Features
- View total received amount
- View total sent amount
- View net balance
- All amounts shown in both crypto and USD values
- Modern, responsive UI
- Real-time wallet analysis

## Prerequisites
- Python 3.8 or higher
- Moralis API key

## Setup

1. Clone the repository:
```bash
git clone <your-repo-url>
cd <repo-name>
```

2. Create a virtual environment and activate it:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the root directory and add your Moralis API key:
```
MORALIS_API_KEY=your_api_key_here
```

## Running the Application

1. Start the Flask API:
```bash
python api.py
```

2. Open `index.html` in your web browser or serve it using a local server:
```bash
# Using Python's built-in server
python -m http.server 8000
```

3. Visit `http://localhost:8000` in your web browser

## Deploying to GitHub Pages

1. Create a new repository on GitHub
2. Push your code to the repository
3. Go to repository Settings > Pages
4. Select the main branch as the source
5. Your site will be published at `https://<username>.github.io/<repo-name>/`

Note: When deploying to GitHub Pages, you'll need to set up a proper backend hosting solution (e.g., Heroku, DigitalOcean) for the Flask API and update the API endpoint in `index.html` accordingly.

## API Endpoints

### POST /analyze
Analyzes a cryptocurrency wallet

Request body:
```json
{
    "wallet": "wallet_address",
    "coin": "coin_symbol"
}
```

Response:
```json
{
    "wallet": "wallet_address",
    "coin": "coin_symbol",
    "received": "100.00000000",
    "receivedUsd": "50,000.00",
    "sent": "50.00000000",
    "sentUsd": "25,000.00",
    "net": "50.00000000",
    "netUsd": "25,000.00"
}
```

## License
MIT

## Credits
- [Moralis](https://moralis.io/) for blockchain data
- [TailwindCSS](https://tailwindcss.com/) for styling 