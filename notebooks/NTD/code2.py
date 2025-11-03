import pandas as pd

# Step 1: Load the Excel file
file_path = 'notebooks/NTD/Supporting Files/NTDdata.xlsx' 
xls = pd.ExcelFile(file_path)
print("Loaded File")

# Step 2: Define the sheet names you want to process
target_sheets = ['UPT', 'VRM', 'VRH', 'VOMS'] 
print("Defined sheet names")

# Step 3: Prepare a dictionary to hold transformed sheets
transformed_sheets = {}
print("Prepared dictionary")

# Step 4: Loop through only the target sheets
for sheet_name in target_sheets:
    df = pd.read_excel(xls, sheet_name=sheet_name)

    # Step 5: Filter rows 
    df_filtered = df[
    (df.iloc[:, 3] == "Active") & 
    (df.iloc[:, 6].astype(str).str.contains("Pittsburgh, PA", case=False, na=False))
    ]


    # Step 6: Separate the first 10 columns (A–J)
    fixed_columns = df_filtered.iloc[:, :10]

    # Step 7: Get the remaining columns (K onward)
    variable_columns = df_filtered.iloc[:, 10:]

    # Step 8: Transform the data
    transformed_data = []
    for index, row in df_filtered.iterrows():
        fixed_part = row.iloc[:10].tolist()
        for col_name in variable_columns.columns:
            new_row = fixed_part + [col_name, row[col_name]]
            transformed_data.append(new_row)

    # Step 9: Create a new DataFrame
    new_columns = list(df.columns[:10]) + ['Date', 'Value']
    transformed_df = pd.DataFrame(transformed_data, columns=new_columns)

    # Step 10: Store the transformed sheet
    transformed_sheets[sheet_name] = transformed_df
    print("Finished Sheet" + sheet_name)

# Step 11: Save all transformed sheets to a new Excel file
with pd.ExcelWriter('transformed_selected_sheets.xlsx', engine='openpyxl') as writer:
    for sheet_name, sheet_df in transformed_sheets.items():
        sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
        print("Saved Sheet" + sheet_name)
