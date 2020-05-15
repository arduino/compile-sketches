import datetime
import json
import os
import pathlib
import unittest.mock

import pytest

import reportsizetrends


# Stub
class Service:
    x = 0

    def spreadsheets(self):
        self.x = 42
        return Service()

    def values(self):
        self.x = 42
        return Service()


reportsizetrends.set_verbosity(enable_verbosity=False)


def get_reportsizetrends_object(fqbn="foo:bar:baz",
                                commit_hash="foohash",
                                commit_url="https://example.com/foo",
                                sketches_data=None,
                                sketches_report_path="foo-sketches-report-path",
                                google_key_file="foo-key-file",
                                spreadsheet_id="foo-spreadsheet-id",
                                sheet_name="foo-sheet-name"):
    # This system is needed to avoid sketches_data having a mutable default argument
    if sketches_data is None:
        sketches_data = [{reportsizetrends.ReportSizeTrends.ReportKeys.sketch: "FooSketch",
                          reportsizetrends.ReportSizeTrends.ReportKeys.flash: 123,
                          reportsizetrends.ReportSizeTrends.ReportKeys.ram: 42}]

    sketches_report = {reportsizetrends.ReportSizeTrends.ReportKeys.fqbn: fqbn,
                       reportsizetrends.ReportSizeTrends.ReportKeys.commit_hash: commit_hash,
                       reportsizetrends.ReportSizeTrends.ReportKeys.commit_url: commit_url}

    # Merge the dictionaries
    sketches_report = {**sketches_report, **sketches_data[0]}

    os.environ["GITHUB_WORKSPACE"] = "/foo/github-workspace"
    with unittest.mock.patch("pathlib.Path.exists", autospec=True, return_value=True):
        with unittest.mock.patch("reportsizetrends.get_sketches_report", autospec=True, return_value=sketches_report):
            report_size_trends_object = reportsizetrends.ReportSizeTrends(sketches_report_path=sketches_report_path,
                                                                          google_key_file=google_key_file,
                                                                          spreadsheet_id=spreadsheet_id,
                                                                          sheet_name=sheet_name)

    return report_size_trends_object


def test_set_verbosity():
    with pytest.raises(TypeError):
        reportsizetrends.set_verbosity(enable_verbosity=2)
    reportsizetrends.set_verbosity(enable_verbosity=True)
    reportsizetrends.set_verbosity(enable_verbosity=False)


@pytest.mark.parametrize("report_path_exists", [True, False])
def test_reportsizetrends(capsys, monkeypatch, mocker, report_path_exists):
    fqbn = "foo:bar:baz"
    commit_hash = "foohash"
    commit_url = "https://example.com/foo"
    sketches_report = {reportsizetrends.ReportSizeTrends.ReportKeys.fqbn: fqbn,
                       reportsizetrends.ReportSizeTrends.ReportKeys.commit_hash: commit_hash,
                       reportsizetrends.ReportSizeTrends.ReportKeys.commit_url: commit_url,
                       reportsizetrends.ReportSizeTrends.ReportKeys.sketch: "FooSketch",
                       reportsizetrends.ReportSizeTrends.ReportKeys.flash: 123,
                       reportsizetrends.ReportSizeTrends.ReportKeys.ram: 42}
    sketches_report_path = "foo/sketches-report-path"
    google_key_file = "foo-key-file"
    spreadsheet_id = "foo-spreadsheet-id"
    sheet_name = "foo-sheet-name"

    monkeypatch.setenv("GITHUB_WORKSPACE", "/foo/github-workspace")

    mocker.patch("pathlib.Path.exists", autospec=True, return_value=report_path_exists)
    mocker.patch("reportsizetrends.get_sketches_report", autospec=True, return_value=sketches_report)

    if report_path_exists is False:
        with pytest.raises(expected_exception=SystemExit, match="1"):
            reportsizetrends.ReportSizeTrends(sketches_report_path=sketches_report_path,
                                              google_key_file=google_key_file,
                                              spreadsheet_id=spreadsheet_id,
                                              sheet_name=sheet_name)
        assert capsys.readouterr().out.strip() == ("::error::Sketches report path: " + sketches_report_path
                                                   + " doesn't exist")
    else:
        report_size_trends = reportsizetrends.ReportSizeTrends(sketches_report_path=sketches_report_path,
                                                               google_key_file=google_key_file,
                                                               spreadsheet_id=spreadsheet_id,
                                                               sheet_name=sheet_name)

        reportsizetrends.get_sketches_report.assert_called_once_with(
            sketches_report_path=reportsizetrends.absolute_path(sketches_report_path)
        )
        assert report_size_trends.fqbn == fqbn
        assert report_size_trends.commit_hash == commit_hash
        assert report_size_trends.commit_url == commit_url
        assert report_size_trends.sketches_data == [sketches_report]
        assert report_size_trends.google_key_file == google_key_file
        assert report_size_trends.spreadsheet_id == spreadsheet_id
        assert report_size_trends.sheet_name == sheet_name


# noinspection PyUnresolvedReferences
def test_report_size_trends():
    google_key_file = "test_google_key_file"
    sketch_path = "foo/SketchPath"
    flash = 42
    ram = 11
    sketches_data = [{reportsizetrends.ReportSizeTrends.ReportKeys.sketch: sketch_path,
                      reportsizetrends.ReportSizeTrends.ReportKeys.flash: flash,
                      reportsizetrends.ReportSizeTrends.ReportKeys.ram: ram}]
    heading_row_data = {}
    current_row = {"populated": False, "number": 42}
    data_column_letters = {"populated": False, "flash": "A", "ram": "B"}

    report_size_trends = get_reportsizetrends_object(google_key_file=google_key_file, sketches_data=sketches_data)

    report_size_trends.get_service = unittest.mock.MagicMock()
    report_size_trends.get_heading_row_data = unittest.mock.MagicMock(return_value=heading_row_data)
    report_size_trends.populate_shared_data_headings = unittest.mock.MagicMock()
    report_size_trends.get_data_column_letters = unittest.mock.MagicMock(return_value=data_column_letters)
    report_size_trends.populate_data_column_headings = unittest.mock.MagicMock()
    report_size_trends.get_current_row = unittest.mock.MagicMock(return_value=current_row)
    report_size_trends.create_row = unittest.mock.MagicMock()
    report_size_trends.write_memory_usage_data = unittest.mock.MagicMock()

    # Test unpopulated shared data headings
    report_size_trends.report_size_trends()

    report_size_trends.get_service.assert_called_once_with(google_key_file=google_key_file)
    report_size_trends.get_heading_row_data.assert_has_calls([unittest.mock.call(), unittest.mock.call()])
    report_size_trends.populate_shared_data_headings.assert_called_once()
    report_size_trends.get_data_column_letters.assert_called_once_with(heading_row_data=heading_row_data)
    report_size_trends.populate_data_column_headings.assert_called_once_with(
        flash_column_letter=data_column_letters["flash"],
        ram_column_letter=data_column_letters["ram"]
    )
    report_size_trends.get_current_row.assert_called_once()
    report_size_trends.create_row.assert_called_once_with(row_number=current_row["number"], sketch_path=sketch_path)
    report_size_trends.write_memory_usage_data.assert_called_once_with(
        flash_column_letter=data_column_letters["flash"],
        ram_column_letter=data_column_letters["ram"],
        row_number=current_row["number"],
        flash=flash,
        ram=ram)

    # Test populated shared data headings
    heading_row_data = {"values": "foo"}
    report_size_trends.get_heading_row_data = unittest.mock.MagicMock(return_value=heading_row_data)
    report_size_trends.populate_shared_data_headings.reset_mock()
    report_size_trends.report_size_trends()
    report_size_trends.populate_shared_data_headings.assert_not_called()

    # Test pre-populated data column headings
    data_column_letters["populated"] = True
    report_size_trends.get_data_column_letters = unittest.mock.MagicMock(return_value=data_column_letters)
    report_size_trends.populate_data_column_headings.reset_mock()
    report_size_trends.report_size_trends()
    report_size_trends.populate_data_column_headings.assert_not_called()

    # Test pre-populated row
    current_row["populated"] = True
    report_size_trends.get_current_row = unittest.mock.MagicMock(return_value=current_row)
    report_size_trends.create_row.reset_mock()
    report_size_trends.report_size_trends()
    report_size_trends.create_row.assert_not_called()


def test_get_heading_row_data():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)
    heading_row_data = "test_heading_row_data"

    Service.get = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock(return_value=heading_row_data)
    report_size_trends.service = Service()

    assert heading_row_data == report_size_trends.get_heading_row_data()
    spreadsheet_range = (sheet_name + "!" + report_size_trends.heading_row_number + ":"
                         + report_size_trends.heading_row_number)
    Service.get.assert_called_once_with(spreadsheetId=spreadsheet_id, range=spreadsheet_range)
    Service.execute.assert_called_once()


def test_populate_shared_data_headings():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, )

    Service.update = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock()
    report_size_trends.service = Service()

    report_size_trends.populate_shared_data_headings()
    spreadsheet_range = (
        sheet_name + "!" + report_size_trends.shared_data_first_column_letter
        + report_size_trends.heading_row_number + ":" + report_size_trends.shared_data_last_column_letter
        + report_size_trends.heading_row_number
    )
    Service.update.assert_called_once_with(
        spreadsheetId=spreadsheet_id,
        range=spreadsheet_range,
        valueInputOption="RAW",
        body={"values": json.loads(
            report_size_trends.shared_data_columns_headings_data)}
    )
    Service.execute.assert_called_once()


def test_get_data_column_letters():
    fqbn = "test_fqbn"

    report_size_trends = get_reportsizetrends_object(fqbn=fqbn)
    heading_row_data = {"values": [["foo", "bar"]]}
    column_letters = report_size_trends.get_data_column_letters(heading_row_data)
    assert column_letters["populated"] is False
    assert "C" == column_letters["flash"]
    assert "D" == column_letters["ram"]

    heading_row_data = {"values": [["foo", report_size_trends.fqbn + report_size_trends.flash_heading_indicator]]}
    column_letters = report_size_trends.get_data_column_letters(heading_row_data)
    assert column_letters["populated"] is True
    assert "B" == column_letters["flash"]
    assert "C" == column_letters["ram"]


def test_populate_data_column_headings():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    fqbn = "test_fqbn"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name, fqbn=fqbn)

    flash_column_letter = "A"
    ram_column_letter = "B"

    Service.update = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock()
    report_size_trends.service = Service()

    report_size_trends.populate_data_column_headings(flash_column_letter=flash_column_letter,
                                                     ram_column_letter=ram_column_letter)
    spreadsheet_range = (sheet_name + "!" + flash_column_letter + report_size_trends.heading_row_number + ":"
                         + ram_column_letter + report_size_trends.heading_row_number)
    board_data_headings_data = ("[[\"" + fqbn + report_size_trends.flash_heading_indicator + "\",\"" + fqbn
                                + report_size_trends.ram_heading_indicator + "\"]]")
    Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                           range=spreadsheet_range,
                                           valueInputOption="RAW",
                                           body={"values": json.loads(board_data_headings_data)})
    Service.execute.assert_called_once()


def test_get_current_row():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    commit_hash = "test_commit_hash"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id,
                                                     sheet_name=sheet_name,
                                                     commit_hash=commit_hash)
    Service.get = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock(return_value={"values": [["foo"], [commit_hash]]})
    report_size_trends.service = Service()

    assert {"populated": True, "number": 2} == report_size_trends.get_current_row()
    spreadsheet_range = (sheet_name + "!" + report_size_trends.commit_hash_column_letter + ":"
                         + report_size_trends.commit_hash_column_letter)
    Service.get.assert_called_once_with(spreadsheetId=spreadsheet_id, range=spreadsheet_range)
    Service.execute.assert_called_once()
    Service.execute = unittest.mock.MagicMock(return_value={"values": [["foo"], ["bar"]]})
    assert {"populated": False, "number": 3} == report_size_trends.get_current_row()


def test_create_row():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    sketch_path = "foo/SketchName"
    sketches_data = [{reportsizetrends.ReportSizeTrends.ReportKeys.sketch: sketch_path}]
    fqbn = "test_fqbn"
    commit_url = "test_commit_url"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id,
                                                     sheet_name=sheet_name,
                                                     sketches_data=sketches_data,
                                                     commit_url=commit_url,
                                                     fqbn=fqbn)
    row_number = 42

    Service.update = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock()
    report_size_trends.service = Service()

    report_size_trends.create_row(row_number=row_number, sketch_path=sketch_path)
    spreadsheet_range = (sheet_name + "!" + report_size_trends.shared_data_first_column_letter + str(row_number)
                         + ":" + report_size_trends.shared_data_last_column_letter + str(row_number))
    shared_data_columns_data = ("[[\"" + '{:%Y-%m-%d %H:%M:%S}'.format(datetime.datetime.now()) + "\",\""
                                + sketch_path + "\",\"=HYPERLINK(\\\"" + report_size_trends.commit_url
                                + "\\\",T(\\\"" + report_size_trends.commit_hash + "\\\"))\"]]")
    Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                           range=spreadsheet_range,
                                           valueInputOption="USER_ENTERED",
                                           body={"values": json.loads(shared_data_columns_data)})
    Service.execute.assert_called_once()


def test_write_memory_usage_data():
    spreadsheet_id = "test_spreadsheet_id"
    sheet_name = "test_sheet_name"
    report_size_trends = get_reportsizetrends_object(spreadsheet_id=spreadsheet_id, sheet_name=sheet_name)
    flash_column_letter = "A"
    ram_column_letter = "B"
    row_number = 42
    flash = 11
    ram = 12

    Service.update = unittest.mock.MagicMock(return_value=Service())
    Service.execute = unittest.mock.MagicMock()
    report_size_trends.service = Service()

    report_size_trends.write_memory_usage_data(flash_column_letter=flash_column_letter,
                                               ram_column_letter=ram_column_letter,
                                               row_number=row_number, flash=flash, ram=ram)
    spreadsheet_range = (sheet_name + "!" + flash_column_letter + str(row_number) + ":"
                         + ram_column_letter + str(row_number))
    size_data = "[[" + str(flash) + "," + str(ram) + "]]"
    Service.update.assert_called_once_with(spreadsheetId=spreadsheet_id,
                                           range=spreadsheet_range,
                                           valueInputOption="RAW",
                                           body={"values": json.loads(size_data)})
    Service.execute.assert_called_once()


def test_get_sketches_report():
    sketches_report_path = pathlib.Path(__file__).resolve().parent.joinpath("testdata", "sketches-report")
    sketches_report = reportsizetrends.get_sketches_report(sketches_report_path=sketches_report_path)
    assert sketches_report == {
        "fqbn": "foo:bar:baz",
        "commit_hash": "foohash",
        "commit_url": "https://example.com/foo",
        "sketch": "FooSketch",
        "flash": 123,
        "ram": 42
    }


@pytest.mark.parametrize("path, expected_absolute_path", [("/asdf", "/asdf"), ("asdf", "/fooWorkspace/asdf")])
def test_absolute_path(monkeypatch, path, expected_absolute_path):
    monkeypatch.setenv("GITHUB_WORKSPACE", "/fooWorkspace")

    assert reportsizetrends.absolute_path(path=path) == pathlib.Path(expected_absolute_path).resolve()
    assert reportsizetrends.absolute_path(path=pathlib.Path(path)) == pathlib.Path(expected_absolute_path).resolve()
