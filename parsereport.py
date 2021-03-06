#!/usr/bin/python3

from pprint import pprint
from optparse import OptionParser
import pandas as pd
import json
import sys
import re
import numpy as np

class Process:

    def __init__(self, options):

        # Configure the layers
        self.layers = ['Unternehmen', 'Abteilung', 'Sub-Abteilung', 'Team', 'Gruppe']

        # Create an empty data
        # master structure
        self.master = {}
        self.master['counts'] = {
            'Vorgesetzter'  : {},
            'Abteilung'     : {},
            'Sub-Abteilung' : {},
            'Team'          : {},
            'Unternehmen'   : {}, 
            'Gruppe'        : {} }
        self.master['tree'] = {}
        self.master['filenames'] = {}
        self.master['id'] = {}
        for layer in self.layers:
            self.master['id'][layer] = {}
        self.master['leaders'] = []
        self.master['span'] = {}

        self.groups = {}
        self.gpt = {}
        self.create_collector(options)
        self.create_vg_tree(options)
        self.create_abt_tree(options)
        #self.create_email_list(options)
        self.get_low_management_span(options)

    def _fix_report_renaming(self, df):
        return df.rename(columns={
            'amtliche Nachname' : 'Nachname',
            })
      
        
    def _get_id(self, name):
        """
        Retruns the unique identifier of the name
        if no itentifier is found, the name is returned
            https://pythex.org
            https://tinyurl.com/yd6p4kbz
        """
        m = re.search('^([A-Z]{2,}|[A-Z]{2}[0-9]{2}|[0-9]{2,})(-| )(.*)', name)
        # DEBUG print(f'{m.group(0)} - {m.group(1)}')
        if m:
            return m.group(1)
        return name

    def _gruppe_id_to_master(self, name):
        self._id_to_master(name, 'Gruppe')

    def _team_id_to_master(self, name):
        self._id_to_master(name, 'Team')

    def _subabteilung_id_to_master(self, name):
        self._id_to_master(name, 'Sub-Abteilung')

    def _unternehmen_id_to_master(self, name):
        self._id_to_master(name, 'Unternehmen')

    def _abteilung_id_to_master(self, name):
        self._id_to_master(name, 'Abteilung')

    def _id_to_master(self, name, layer):
        m = re.search('^([A-Z]{2,}|[A-Z]{2}[0-9]{2}|[0-9]{2,})-(.*)', name)
        i = m.group(1)
        t = m.group(2)
        if i not in self.master['id'][layer]:
            self.master['id'][layer][i] = []
        if t not in self.master['id'][layer][i]:
            self.master['id'][layer][i].append(t)
            if layer == "Unternehmen":
                # DEBUG 
                print (f"< {i} ({t}) > {layer} ")

    def drop_unwanted_columns(self, df, keep=[]):

        # The SurveyMonkey report might have unwanted rows
        for column_name in df.columns.tolist():
            if column_name in keep:
                continue
            df = df.drop(columns=[column_name])
        return df

    def gen_groups(self, name):
        id_nr   = name.split('-', 1)[0]
        id_name = name.split('-', 1)[1]
        if id_nr not in self.groups:
            self.groups[id_nr] = [id_name]
            return name
        elif id_name not in self.groups[id_nr]:
            self.groups[id_nr].append(id_name)

    def name_split(self, name):
        n_short = name.split('-', 1)[0]
        n_name  = name.split('-', 1)[1]
        return f'{n_short} | {n_name}'

    def rename_groups(self, name):
        id_nr   = name.split('-', 1)[0]
        id_name = name.split('-', 1)[1]
        ret = f'{id_nr}'
        for n in self.groups[id_nr]:
            ret = ret + " | " + n
        return ret

    def create_abt_tree(self, options):

        df = pd.read_csv(options.filename)
        df = self._fix_report_renaming(df)
           
        
        keep = [
            'Nachname',
            'Vorname',
            'Sub-Abteilung',
            'Unternehmen'
            ]

        for column_name in df.columns.tolist():
            if column_name not in keep:
                df = df.drop(columns=[column_name])

        df = df.loc[df['Nachname'].notna()]
        df['Mitarbeiter']  = df.apply(lambda row: row['Nachname'] + ", " + row['Vorname'], axis=1)
        df = df.loc[df['Mitarbeiter'].notna()]

        df = df.drop(columns=['Nachname', 'Vorname'])
        #print( df.columns.tolist())

        df.to_json('collector-abt.json')

        self.master['ma-to-abt'] = json.loads(df.to_json())

    def create_vg_email_list(self, options):
        """list bottom leaders with low management span
        """
        self.master['vg-email'] = {}
        email = 'Geschäftlich  Informationen zur E-Mail E-Mail-Adresse'
        df = pd.read_csv(options.filename)
        df = self._fix_report_renaming(df)
        df = df.loc[df['Nachname'].notna()]
        df['Mitarbeiter']  = df.apply(lambda row: row['Nachname'] + ", " + row['Vorname'], axis=1)
        df = df.loc[df['Mitarbeiter'].notna()]
        vgl = df['Vorgesetzter'].unique().tolist()
        ceo = None
        for vg in vgl:
            for idx, ma in df.loc[(df['Mitarbeiter'] == vg)].iterrows():
                self.master['vg-email'][ma['Mitarbeiter']] = ma[email]
                self.master['vg-email'][vg] = ma[email]

        for idx, ma in df.loc[(df['Vorgesetzter'].isnull())].iterrows():
            self.master['vg-email'][ma['Mitarbeiter']] = ma[email]



    def get_low_management_span(self, options):
        """list bottom leaders with low management span
        """

        df = pd.read_csv(options.filename)
        df = self._fix_report_renaming(df)
        df = df.loc[df['Nachname'].notna()]
        df['Mitarbeiter']  = df.apply(lambda row: row['Nachname'] + ", " + row['Vorname'], axis=1)
        df = df.loc[df['Mitarbeiter'].notna()]
        vgl = df['Vorgesetzter'].unique().tolist()

        ret = {}

        # Go through all leaders
        for vg in vgl:

            # Remove empty values (might be CEO)
            if type(vg) != str:
                
                # CEO hack
                self.master['ceo'] = vg
                
                continue

            vn = 0
            fs = 0
            for idx, ma in df.loc[(df['Vorgesetzter'] == vg)].iterrows():
                if ma['Mitarbeiter'] in vgl:
                    vn += 1

                else:
                    fs += 1

            self.master['span'][vg] = {'staff' : fs, 'leader' : vn}
            if (vn == 0 and fs < 3):
                ret[vg] = fs
            elif ( fs < 3 and fs > 0):
                print(vg, fs, vn)

        #pprint(self.master['span'])

    def create_vg_tree(self, options):

        df = pd.read_csv(options.filename)
        df = self._fix_report_renaming(df)
        df = df.loc[df.Mitarbeitergruppe != 'Lernende']
        df = df.loc[df['Mitarbeitergruppe'].notna()]

        cols = [
            'Nachname',
            'Vorname',
            'Vorgesetzter',
            'Unternehmen',
            'Abteilung',
            'Sub-Abteilung',
            'Team',
            'Gruppe',
            ]

        for column_name in df.columns.tolist():
            if column_name not in cols:
                df = df.drop(columns=[column_name])

        df['Gruppe'].map(self._gruppe_id_to_master)
        df['Team'].map(self._team_id_to_master)
        df['Sub-Abteilung'].map(self._subabteilung_id_to_master)
        df['Abteilung'].map(self._abteilung_id_to_master)
        df['Unternehmen'].map(self._unternehmen_id_to_master)

        #print(df['Unternehmen'])
        
        # Reduce all columnes used as layer to the ID
        for layer in self.layers:
            df[layer] = df[layer].map(self._get_id)

        #print(df['Unternehmen'])            
            
        # Get list of all leaders
        self.master['leaders'] = df['Vorgesetzter'].unique().tolist()

        # Count all Filters
        for col in self.master['counts']:
            print(f'COL: ({col})')
            for name, cnt in df.groupby(col).count()['Nachname'].iteritems():
                # DEBUG if col == "Unternehmen":
                #    print (name)
                self.master['counts'][col][name.split(' | ')[0]] = cnt

        df['Mitarbeiter']  = df.apply(lambda row: row['Nachname'] + ", " + row['Vorname'], axis=1)
        df = df.loc[df['Mitarbeiter'].notna()]

        for vg in self.master['leaders']:
            self.master['tree'][vg] = []
            if type(vg) != str:
                # CEO
                continue

            print(vg)
                
            ret  = df.loc[ (df['Mitarbeiter'] == vg) ]
            name = ""
            print( self.layers)
            for layer in self.layers:
                """
                    No problem: 
                    > Catch problems with empty lines in the file: "","","","","","","","","",""
                    > Catch problems with external admins (Marcus) "Marcus"...
                    Problems:
                    > Problem found in SF data
                """

                name += ret[layer].values[0] + "-"

            try:
                name += vg.replace(', ', '-') + ".xlsx"
                print(name)
                self.master['filenames'][vg] = name.replace(' ', '-')
            except IndexError as e:
                print(f'>>> ERROR {e}')
                print(f'>>> VG: {vg} MA: {name}')
                print(f'>>> hint: often the VG is no longer employee, problem in data source')
                sys.exit(-1)

            vn = 0
            fs = 0
            mas = df.loc[ (df['Vorgesetzter'] == vg) ]
            for idx,ma in mas.iterrows():
                name = ma['Mitarbeiter']
                if name in self.master['leaders']:
                    self.master['tree'][vg].append(name)
                    vn += 1
                    fs += 1
                else:
                    fs += 1


    def write_master_to_json(self, name = 'master'):
        """
        Write the master data to a json file for post-processing
        """
        print(f'> write: {name}.json')
        with open(f'{name}.json', 'w') as outfile:
            json.dump(self.master, outfile, indent=4)


    def create_collector(self, options):

        df = pd.read_csv(options.filename)
        df = self._fix_report_renaming(df)

        df = self.drop_unwanted_columns(df, [
            'Geschäftlich  Informationen zur E-Mail E-Mail-Adresse',
            'Abteilung',
            'Team',
            'Gruppe',
            'Nachname',
            'Vorname',
            'Vorgesetzter',
            'Mitarbeitergruppe'])

        df = df.loc[df.Mitarbeitergruppe != 'Lernende']
        df = df.loc[df['Mitarbeitergruppe'].notna()]

        df = df.drop(columns=['Mitarbeitergruppe'])

        vg = df['Vorgesetzter'].str.split(", ", n = 1, expand = True)
        df["VG-LAST"] = vg[0]
        df["VG-FIRST"]= vg[1]

        for leader in df['Vorgesetzter'].unique():
            leader_group = df.loc[(df['Vorgesetzter'] == leader) ]
            groups = leader_group['Gruppe'].unique()
            #if len(groups) > 1:
                #print(leader_group['Vorgesetzter'].unique(), leader_group['Gruppe'].unique())


        df = df.rename(columns={
            'Nachname' : 'LAST',
            'Vorname'  : 'FIRST',
            'Geschäftlich  Informationen zur E-Mail E-Mail-Adresse' : 'EMAIL',
            'Abteilung' : 'ABTEILUNG',
            'Team' : 'TEAM',
            'Gruppe' : 'GRUPPE',
            })

        df = df.reindex([
            'EMAIL',
            'FIRST',
            'LAST',
            'VG-FIRST',
            'VG-LAST',
            'ABTEILUNG',
            'TEAM',
            'GRUPPE',
            ], axis=1)

        df['GRUPPE'].map(self.gen_groups)
        df['GRUPPE'] = df['GRUPPE'].map(self.rename_groups)
        df['ABTEILUNG'] = df['ABTEILUNG'].map(self.name_split)
        df['TEAM'] = df['TEAM'].map(self.name_split)

        df.to_csv('collector-data.csv', index=False)

if __name__ == "__main__":

    parser = OptionParser()

    parser.add_option("-v", "--verbose",
        action="store_true", dest="verbose", default="False",
        help="Verbose prints enabled")

    parser.add_option("-f", "--file", dest="filename",
                  help="write report to FILE", metavar="FILE")

    (options, args) = parser.parse_args()

    run = Process(options)
    run.create_vg_email_list(options)
    run.write_master_to_json()
    run.create_collector(options)
