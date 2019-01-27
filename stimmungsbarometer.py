#!/usr/bin/python3

from pprint import pprint
from optparse import OptionParser
import pandas as pd
import json
import sys
import re

def get_id(name):

    """
    https://pythex.org
    https://tinyurl.com/yd6p4kbz
    """
    m = re.search('^([A-Z]{2,}|[0-9]{2,})', name)
    if m:
        return m.group(0)
    return name


def read_survey(options):


    df = pd.read_csv(options.filename)

    # Remove SurveyMonkey columns not required
    df = df.drop(columns=['respondent_id',
                          'collector_id',
                          'date_created',
                          'date_modified',
                          'ip_address',
                          ])

    # TODO remove unknown columns, to be checked
    df = df.drop(columns=['Name',
                          'Boss Name'])

    # open master data
    with open('master.json') as json_file:
        master = json.load(json_file)

    # Rename columns
    df = df.rename(columns={
        'Gebe bitte an, wie zufrieden du bist als Angestellte/r von digitec/Galaxus. Die Skala geht von 1 (schlechtester Wert) bis 10 (bester Wert).Indique ton degré de satisfaction en tant qu’employé(e) digitec/Galaxus. L’échelle va de 1 (la moins bonne note) à 10 (la meilleure note).' : 'Stimmungswert',
        'Was motiviert dich an deinem Job besonders, was trägt besonders zu deiner Zufriedenheit bei?Qu’est-ce qui te motive spécialement dans ton travail, qu’est-ce qui contribue particulièrement à ta satisfaction ?' : 'Motivation 1',
        'Unnamed: 24': 'Motivation 2',
        'Was müsste man verbessern, damit du (noch) zufriedener wärst?Que devrait-on améliorer pour que tu sois (encore) plus satisfait(e)?': 'Verbesserung 1',
        'Unnamed: 26': 'Verbesserung 2',
        'email_address': 'EMAIL',
        'custom_1' : 'VGFIRST',
        'custom_2' : 'VGLAST',
        'custom_3' : 'Abteilung',
        'custom_4' : 'Team',
        'custom_5' : 'Gruppe'
        })


    # Merge all values (unamed columns 14 to 22) into one
    for idx in range (14, 23):
        df['Stimmungswert'] = df['Stimmungswert'].fillna(df[f'Unnamed: {idx}'])

    # Drop the unnamed columns 14 to 22)
    df = df.drop(columns= ['Unnamed: %s' % x for x in range(14,23)])

    # Delte Row 2 some helper text
    df = df.drop(df.index[0])

    df['Stimmungswert'] = df['Stimmungswert'].astype(int)
    df['Vorgesetzter']  = df.apply(lambda row: row['VGLAST'] + ", " + row['VGFIRST'], axis=1)
    df['Mitarbeiter']   = df.apply(lambda row: row['last_name'] + ", " + row['first_name'], axis=1)

    abt = pd.read_json('collector-abt.json')
    df = pd.merge(df, abt, on='Mitarbeiter')


    # Calculate all filters
    filters = ['Vorgesetzter', 'Gruppe', 'Team', 'Sub-Abteilung', 'Abteilung']
    for name in filters:
        df[f'{name}-Mean'] = df[name]
        df[f'{name}-Count'] = df[name]
        df[f'{name}-Max'] = df[name]
        # for compatiblity, master file is based on id name only:
        df[f'{name}-Max'] = df[f'{name}-Max'].map(get_id)
        mean  = df.groupby(name).mean(numeric_only=True).to_dict()['Stimmungswert']
        count = df.groupby(name).count()['Stimmungswert'].to_dict()
        df = df.replace({f'{name}-Mean' : mean})
        df = df.replace({f'{name}-Count': count})
        df = df.replace({f'{name}-Max'  : master['counts'][name]})
        df[f'{name}-%'] = df.loc[:,f'{name}-Count'].astype(int) / df.loc[:,f'{name}-Max'].astype(int)

    """
    v1 = df.groupby('Vorgesetzter').mean(numeric_only=True)
    v2 = df.groupby('Gruppe').mean(numeric_only=True)
    v3 = df.groupby('Team').mean(numeric_only=True)
    v4 = df.groupby('Abteilung').mean(numeric_only=True)
    v5 = df.groupby('Sub-Abteilung').mean(numeric_only=True)

    c1 = df.groupby('Vorgesetzter').count()['Stimmungswert']
    c2 = df.groupby('Gruppe').count()['Stimmungswert']
    c3 = df.groupby('Team').count()['Stimmungswert']
    c4 = df.groupby('Abteilung').count()['Stimmungswert']
    c5 = df.groupby('Sub-Abteilung').count()['Stimmungswert']

    df['Gruppe-Mean'] = df['Gruppe']
    df['Gruppe-Count'] = df['Gruppe']

    df['Vorgesetzter-Mean'] = df['Vorgesetzter']
    df['Vorgesetzter-Count'] = df['Vorgesetzter']

    df['Team-Mean'] = df['Team']
    df['Team-Count'] = df['Team']

    df['Abteilung-Mean'] = df['Abteilung']
    df['Abteilung-Count'] = df['Abteilung']

    df['Sub-Abteilung-Mean'] = df['Sub-Abteilung']
    df['Sub-Abteilung-Count'] = df['Sub-Abteilung']

    df = df.replace({'Vorgesetzter-Mean'  : v1.to_dict()['Stimmungswert']})
    df = df.replace({'Vorgesetzter-Count' : c1.to_dict()})

    df = df.replace({'Gruppe-Mean'  : v2.to_dict()['Stimmungswert']})
    df = df.replace({'Gruppe-Count' : c2.to_dict()})

    df = df.replace({'Team-Mean'  : v3.to_dict()['Stimmungswert']})
    df = df.replace({'Team-Count'  : c3.to_dict()})

    df = df.replace({'Abteilung-Mean'  : v4.to_dict()['Stimmungswert']})
    df = df.replace({'Abteilung-Count'  : c4.to_dict()})

    df = df.replace({'Sub-Abteilung-Mean'  : v5.to_dict()['Stimmungswert']})
    df = df.replace({'Sub-Abteilung-Count'  : c5.to_dict()})
    """

    def rec_add_to(name, res, vglst):
        res.append(name)
        for subname in vglst[name]:
            rec_add_to(subname, res, vglst)
        return res

    with open('collector-vg-fnames.json') as json_file:
        fnames = json.load(json_file)

    with open('collector-vg-tree.json') as json_file:
        vgl = json.load(json_file)
        for vg in vgl:

            vg = "Teuteberg, Florian"

            print(f">>> Vorgesetzter: {vg}")

            if vg == "NaN":
                # CEO
                continue

            name = fnames[vg]

            res = []
            res = rec_add_to(vg, res, vgl)

            dfl = df.copy(deep=True)
            dfl = dfl.loc[ dfl['Vorgesetzter'].isin(res)]

            # open the XLSX writer
            writer = pd.ExcelWriter(name, engine='xlsxwriter')

            # for each filter
            #x = ['Vorgesetzter', 'Gruppe', 'Team', 'Sub-Abteilung', 'Abteilung']

            for filter in filters:
                #print(f'>>> Filter: {filter} - with min number of respones: {options.min_nr_of_resp}')

                sheet  = filter

                dfc= dfl.copy(deep=True)

                col_idx = [
                    filter,
                    'Stimmungswert',
                    f'{filter}-Mean',
                    f'{filter}-Count',
                    f'{filter}-Max',
                    f'{filter}-%',
                    'Motivation 1',
                    'Motivation 2',
                    'Verbesserung 1',
                    'Verbesserung 2'
                    ]

                dfc = dfl.reindex(col_idx, axis=1)

                # Remove all responses where its count is below minimum
                # --------------------------------------------------------------

                # Remove all rows where the response cound is to low
                # independant of the management hierarchie
                dfc = dfc.loc[dfc[f'{filter}-Count'] > options.min_nr_of_resp]

                # Check the number of responses based on the current filter
                # ... this is special case when the filter removes some values
                # ... from the total count. Occures when the same group id
                # ... is used over different management levels

                if not dfc.empty:
                    # if not already empty, check all single reports

                    # get the counts grouped by the column with the name of
                    # the filter and add it to the new column Filter-Count
                    c = dfc.groupby(filter).count()['Stimmungswert']
                    dfc['Filter-Count'] = df[filter]
                    dfc = dfc.replace({'Filter-Count' : c.to_dict()})
                    # Drop all rows where the Filter-Count is below the min
                    dfc = dfc.loc[dfc['Filter-Count'] > options.min_nr_of_resp]


                # Write dataframe to the xlsx sheet
                # --------------------------------------------------------------

                # add data frame to sheet
                dfc.to_excel(writer, sheet)

                last_row = dfc.shape[0] - 1
                last_col = dfc.shape[1] - 1

                # define and set number formats
                workbook  = writer.book
                worksheet = writer.sheets[sheet]

                #https://xlsxwriter.readthedocs.io/worksheet.html#autofilter
                worksheet.autofilter(0, 0, last_row, last_col)

                text_format = workbook.add_format()
                text_format.set_text_wrap()

                worksheet.set_column(col_idx.index('Motivation 1') + 1,
                                     col_idx.index('Verbesserung 2') + 1,
                                     width = 40,
                                     cell_format = text_format
                                     )


            # final save
            writer.save()

            break

if __name__ == "__main__":

    parser = OptionParser()

    parser.add_option("-v", "--verbose",
        action="store_true", dest="verbose", default="False",
        help="Verbose prints enabled")

    parser.add_option("-x", "--exclude",
        type="int", dest="min_nr_of_resp", default="3")

    parser.add_option("-f", "--file", dest="filename",
                  help="write report to FILE", metavar="FILE")

    parser.add_option("-m", "--mode", dest="mode",
                  help="vorgesetzter, abteilung, team, gruppe")

    (options, args) = parser.parse_args()

    read_survey(options)
