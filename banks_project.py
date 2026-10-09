import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
import numpy as np
import sqlite3


def log_progress(message):
    timestamp = datetime.now().strftime('%Y-%b-%d-%H:%M:%S')
    with open('code_log.txt', 'a', encoding='utf-8') as f:
        f.write(timestamp + ',' + message + '\n')


def extract(url, table_attribs=None):
    if table_attribs is None:
        table_attribs = ['Name', 'Market cap (US$ billion)']

    response = requests.get(url, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')

    heading = soup.find(id='By_market_capitalization')
    if heading is None:
        raise ValueError('Market capitalization heading not found')

    table = heading.find_next('table')
    if table is None:
        raise ValueError('Market capitalization table not found')

    data = []

    for row in table.find_all('tr'):
        cells = row.find_all('td')

        if len(cells) >= 3:
            name = cells[1].get_text(strip=True)
            market_cap = cells[2].get_text()

            if market_cap.endswith('\n'):
                market_cap = market_cap[:-1]

            market_cap = float(market_cap.strip())
            data.append([name, market_cap])

    df = pd.DataFrame(data, columns=table_attribs)
    df.rename(
        columns={'Market cap (US$ billion)': 'MC_USD_Billion'},
        inplace=True
    )

    log_progress('Data extraction complete')
    return df


def transform(df, csv_path):
    exchange_rate_df = pd.read_csv(csv_path)
    exchange_rate = exchange_rate_df.set_index('Currency').to_dict()['Rate']

    gbp_rate = float(exchange_rate['GBP'])
    eur_rate = float(exchange_rate['EUR'])
    inr_rate = float(exchange_rate['INR'])

    df['MC_GBP_Billion'] = [
        np.round(x * gbp_rate, 2) for x in df['MC_USD_Billion']
    ]
    df['MC_EUR_Billion'] = [
        np.round(x * eur_rate, 2) for x in df['MC_USD_Billion']
    ]
    df['MC_INR_Billion'] = [
        np.round(x * inr_rate, 2) for x in df['MC_USD_Billion']
    ]

    log_progress('Data transformation complete')
    return df


def load_to_csv(df, output_path):
    df.to_csv(output_path, index=False)
    log_progress(f'Data saved to CSV: {output_path}')


def load_to_db(df, sql_connection, table_name):
    df.to_sql(
        table_name,
        sql_connection,
        if_exists='replace',
        index=False
    )
    log_progress(f'Data loaded to database table: {table_name}')


def run_query(query_statement, sql_connection):
    print('\nQuery:', query_statement)
    query_output = pd.read_sql_query(query_statement, sql_connection)
    print(query_output.to_string(index=False))
    log_progress(f'Query executed: {query_statement}')


if __name__ == '__main__':
    url = (
        'https://web.archive.org/web/20230908091635/'
        'https://en.wikipedia.org/wiki/List_of_largest_banks'
    )
    table_attribs = ['Name', 'Market cap (US$ billion)']

    log_progress('ETL process started')

    df = extract(url, table_attribs)
    df = transform(df, 'exchange_rate.csv')

    load_to_csv(df, 'Largest_banks_data.csv')

    sql_connection = sqlite3.connect('Banks.db')
    log_progress('Database connection initiated')

    try:
        load_to_db(df, sql_connection, 'Largest_banks')

        run_query(
            'SELECT * FROM Largest_banks',
            sql_connection
        )
        run_query(
            'SELECT AVG(MC_GBP_Billion) FROM Largest_banks',
            sql_connection
        )
        run_query(
            'SELECT Name FROM Largest_banks LIMIT 5',
            sql_connection
        )
    finally:
        sql_connection.close()
        log_progress('Database connection closed')

    log_progress('ETL process complete')