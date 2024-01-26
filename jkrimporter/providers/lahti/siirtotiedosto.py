import logging
import csv
from pathlib import Path
from typing import List

from jkrimporter.datasheets import SiirtotiedostoSheet
from jkrimporter.providers.lahti.models import Asiakas
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class AsiakastiedotSheet(SiirtotiedostoSheet[Asiakas]):
    @staticmethod
    def _obj_from_dict(data):
        return Asiakas.parse_obj(data)


class LahtiSiirtotiedosto:
    def __init__(self, path):
        self._path = path

    @classmethod
    def readable_by_me(cls, path):
        directory = Path(path)
        for file in directory.iterdir():
            if file.is_file() and file.suffix == ".csv":
                return True
        return False

    @property
    def asiakastiedot(self):
        all_data = []
        asiakas_list = []
        failed_validations = []
        missing_headers_list = []
        expected_headers = [
                            'UrakoitsijaId', 'UrakoitsijankohdeId', 'Kiinteistotunnus',
                            'Kiinteistonkatuosoite', 'Kiinteistonposti', 'Haltijannimi',
                            'Haltijanyhteyshlo', 'Haltijankatuosoite', 'Haltijanposti',
                            'Haltijanmaakoodi', 'Haltijanulkomaanpaikkakunta', 'Pvmalk',
                            'Pvmasti', 'tyyppiIdEWC', 'COUNT(kaynnit)',
                            'SUM(astiamaara)', 'koko', 'SUM(paino)', 'tyhjennysvali',
                            'kertaaviikossa', 'kertaaviikossa2', 'Voimassaoloviikotalkaen',
                            'Voimassaoloviikotasti', 'palveluKimppakohdeId',
                            'KimpanNimi', 'Kimpankatuosoite', 'Kimpanposti', 'Kuntatun'
                        ]

        # Iterate through all CSV files in the directory to check headers
        for csv_file_path in Path(self._path).glob("*.csv"):
            with open(csv_file_path, mode="rb") as csv_file:
                # Read the content and handle BOM
                content = csv_file.read()
                if content.startswith(b'\xef\xbb\xbf'):
                    content = content[3:]
                content = content.decode("cp1252")
                csv_reader = csv.DictReader(content.splitlines(), delimiter=";", quotechar='"', skipinitialspace=True)
                headers = csv_reader.fieldnames
                missing_headers = [header for header in expected_headers if header not in headers]

                if missing_headers:
                    missing_headers_list.append({
                        'file_path': csv_file_path,
                        'headers': headers
                    })

        if missing_headers_list:
            for file in missing_headers_list:
                print(f"Tiedosto: {file['file_path']}, oletetut sarakeotsikot puuttuvat: {file['headers']}")
            raise RuntimeError("Osassa tiedostoissa oletetut sarakeotsikot puuttuvat.")

        # Iterate through all CSV files in the directory
        for csv_file_path in Path(self._path).glob("*.csv"):
            with open(csv_file_path, mode="rb") as csv_file:
                # Read the content and handle BOM
                content = csv_file.read()
                if content.startswith(b'\xef\xbb\xbf'):
                    content = content[3:]
                content = content.decode("cp1252")
                csv_reader = csv.DictReader(content.splitlines(), delimiter=";", quotechar='"', skipinitialspace=True)
                data_list = [row for row in csv_reader]
                all_data.extend(data_list)

        for data in all_data:
            # Validate Asiakas, if validation fails, append to failed_validations
            try:
                asiakas_obj = Asiakas.parse_obj(data)
                asiakas_list.append(asiakas_obj)
            except ValidationError as e:
                logger.error(f"Asiakas-objektin luonti epäonnistui datalla: {data}. Virhe: {e}")
                failed_validations.append(data)

        # Save failed validations to a new CSV file in a subdirectory
        output_directory = csv_file_path.parent
        output_file_path = output_directory / "kohdentumattomat.csv"

        with open(output_file_path, mode="w", encoding="cp1252", newline="") as output_csv_file:
            csv_writer = csv.DictWriter(output_csv_file, expected_headers, delimiter=";", quotechar='"')
            csv_writer.writeheader()
            if failed_validations:
                # Filter out columns not in expected_headers
                filtered_failed_validations = [
                    {key: value for key, value in data.items() if key in expected_headers}
                    for data in failed_validations
                ]

                csv_writer.writerows(filtered_failed_validations)

        return asiakas_list
