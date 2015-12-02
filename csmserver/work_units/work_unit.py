class WorkUnit(object):

    def process(self, db_session, logger, process_name):
        raise NotImplementedError("Children must override Process")

