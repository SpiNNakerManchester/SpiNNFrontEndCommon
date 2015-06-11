from threading import Lock
import os
from data_specification.file_data_writer import FileDataWriter


_data_spec_report_lock = Lock()


def get_data_spec_report_writer(placement, report_folder):
    """ Create data spec report writer with file name generated
        from the placement and machine name

    :param placement: The placement of the vertex for which the data is being\
                generated
    :param machine_name: The name of the machine for which the data is being\
                generated
    :param report_folder: The folder into which reports are to be written
    :return: The report writer
    """

    # Ensure the data spec text files folder exists in the reports
    report_subfolder = os.path.join(report_folder, "data_spec_text_files")
    _data_spec_report_lock.acquire()
    if not os.path.exists(report_subfolder):
        os.makedirs(report_subfolder)
    _data_spec_report_lock.release()

    file_name = "dataSpec_{}_{}_{}.txt".format(
        placement.x, placement.y, placement.p)
    binary_file_path = os.path.join(report_subfolder, file_name)
    return FileDataWriter(binary_file_path)


def get_data_spec_data_writer(placement, output_folder):
    """ Create data spec output writer with file name generated\
        from the placement and machine name

    :param placement: The placement of the vertex for which the data is being\
                generated
    :param machine_name: The name of the machine for which the data is being\
                generated
    :param output_folder: The folder into which data is to be written
    :param write_text_specs: Determines if the report is to be written
    :return: A tuple of (data file name, data writer)
    """
    file_name = "dataSpec_{}_{}_{}.dat".format(
        placement.x, placement.y, placement.p)
    binary_file_path = os.path.join(output_folder, file_name)
    return (binary_file_path, FileDataWriter(binary_file_path))
