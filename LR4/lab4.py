import datetime
import sqlite3
import xmlrpc.client

import dateutil
import pandas as pd
import plotly.express as px
import streamlit as st

stat_server2 = xmlrpc.client.ServerProxy("http://localhost:8038")

start_date_val = datetime.date.today().replace(day=1)
end_date_val = datetime.date.today() + dateutil.relativedelta.relativedelta(day=31)

st.write("""
# Аналитика работы веб-сервиса
""")

st.sidebar.header('Ввод данных')


def user_input_features():
    start_date = st.sidebar.date_input('Начальная дата', value=start_date_val, min_value=start_date_val,
                                       max_value=end_date_val)
    end_date = st.sidebar.date_input('Конечная дата', value=end_date_val, min_value=start_date_val,
                                     max_value=end_date_val)

    interval_width = st.sidebar.slider('Интервал анализа, час', 1, 24, 4)
    proc_type = st.sidebar.text_input("Тип операции")
    data = {'start_date': start_date,
            'end_date': end_date,
            'interval_width': interval_width,
            'proc_type': proc_type.strip()}
    features = pd.DataFrame(data, index=[0])

    return features


user_input_data = user_input_features()


@st.cache_resource
def get_df_from_log():
    conn = sqlite3.connect('log.db')
    query = 'SELECT * FROM log'
    cursor = conn.execute(query)
    df = pd.DataFrame(cursor.fetchall(), columns=['op_type', 'date', 'eval_time'])
    conn.close()
    return df


def apply_conditions_to_df(df, op_type, par_start_date, par_end_date):
    conditions = []
    if op_type != '':
        conditions.append('op_type == @op_type')
    if par_start_date != '':
        conditions.append('date >= @par_start_date')
    if par_end_date != '':
        conditions.append('date <= @par_end_date')
    str_conditions = " and ".join(conditions)
    return df.query(str_conditions)


def process_data(log_df, input_data):
    op_type = input_data.iloc[0]['proc_type']
    start_date = input_data.iloc[0]['start_date']
    end_date = input_data.iloc[0]['end_date']
    if start_date >= end_date:
        st.write('Начальная дата должна быть меньше конечной хотя бы на один день')
        st.stop()

    return apply_conditions_to_df(log_df, op_type, start_date.strftime("%Y-%m-%d %H:%M:%S"),
                                  end_date.strftime("%Y-%m-%d 23:59:59"))


def get_unused_hours(used_hours, interval):
    time_intervals = range(0, 24, interval)
    proceed_hours = [time_intervals[i] for i in range(len(time_intervals)) if time_intervals[i] not in used_hours]
    return proceed_hours


def count_calls_by_day(data, interval):
    df = pd.DataFrame(data)
    del df['eval_time']
    df.date = pd.to_datetime(df.date).dt.strftime('1-1-1 %H:%M:%S')
    df.date = pd.to_datetime(df.date)
    df = df.groupby(
        [pd.Grouper(key='date', freq=str(interval) + 'h'), 'op_type'])
    df = df.size().reset_index(name='count')

    df.date = df.date.dt.hour
    df = df.pivot(index='date', columns='op_type', values='count')

    used_hours = df.index.values
    proceed_hours = get_unused_hours(used_hours, interval)
    df = pd.concat(
        [df, pd.DataFrame(index=proceed_hours, columns=df.columns).fillna(0)])
    return df


log_data = get_df_from_log()

proceed_data = process_data(log_data, user_input_data)

st.subheader('Введенные данные')
st.write(user_input_data)

st.subheader('Все данные лог-файлов')
st.write(log_data)

st.subheader('Отобранные данные лог-файлов')
st.write(proceed_data)

st.subheader('Гистограмма по количеству вызовов для типа операции')
st.bar_chart(proceed_data['op_type'].value_counts())

st.subheader('Гистограмма по количеству вызовов для типа операций на сутки за заданный интервал')
interval_width_val = int(user_input_data.iloc[0]['interval_width'])
df_count_calls_by_day = count_calls_by_day(proceed_data, interval_width_val)

st.bar_chart(df_count_calls_by_day)

st.subheader('Круговая диаграмма по количеству вызовов типа операции')
df_count_calls = proceed_data['op_type'].value_counts(normalize=True)
df_count_calls = pd.DataFrame(df_count_calls)
df_count_calls = df_count_calls.reset_index()
df_count_calls.columns = ['op_type', 'count']
fig = px.pie(df_count_calls, values='count', names='op_type')
st.plotly_chart(fig)

st.subheader('Круговая диаграмма по времени вызовов типа операции')
df_eval_time = proceed_data.groupby('op_type')['eval_time'].agg('sum')
df_eval_time = pd.DataFrame(df_eval_time)
df_eval_time = df_eval_time.reset_index()
df_eval_time.columns = ['op_type', 'eval_time']

fig = px.pie(df_eval_time, values='eval_time', names='op_type')
st.plotly_chart(fig)
