import pandas as pd
file_path = 'your_excel_file.xlsx'  # Replace with your actual file path
df = pd.read_excel(file_path, engine='openpyxl')

fixed_columns = df.iloc[:, :10]
variable_columns = df.iloc[:, 10:]
transformed_data = []

df_filtered = df[df.iloc[:, 6] == "Pittsburgh, PA"]
df_filtered = df[df.iloc[:, 3] == "Active"]

for index, row in df.iterrows():
    fixed_part = row.iloc[:10].tolist()
    
    for col_name in variable_columns.columns:
        new_row = fixed_part + [col_name, row[col_name]]
        transformed_data.append(new_row)

new_columns = list(df.columns[:10]) + ['Date', 'UPT']
transformed_df = pd.DataFrame(transformed_data, columns=new_columns)
