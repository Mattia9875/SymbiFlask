from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api
from flask_marshmallow import Marshmallow
from celerytask import RunSymbiFlow
from celery.result import AsyncResult
import os, json, shutil

app = Flask(__name__)
api = Api(app)
# Configuring the database path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# database object
db = SQLAlchemy(app)
# marshmallow object
ma = Marshmallow(app)


# function to recursively delete a project dir
def RecursiveHDLDelete(query_id, dir_name):
    try:
        # gather record list
        db_list = HDL_file.query.filter_by(Project_id=query_id).all()
        # delete directory
        shutil.rmtree(dir_name, ignore_errors=True)
        # cycle records
        for row in db_list:
            db.session.delete(row)
    except Exception as e:
        print(e)
        raise "Recursive delete failed"
        return
    else:
        return


# function to set up symbiflow
def SymbiflowHelper(data, mode):
    # gather data from the database
    fpga_data = FPGA.query.get(data.FPGA_id)
    top_level = HDL_file.query.filter_by(Project_id=data.id, top_level_flag=True).first()
    # FPGA model
    PART_NAME = fpga_data.model_id
    # top level entity file
    TOP_FILE = top_level.file_name
    # container project folder
    PRJ_DIR = os.path.join("/symb", data.Project_name + "_" + fpga_data.model_id)
    # host project folder
    PRJ_DIR_HOST = os.path.join(os.getcwd(), data.Project_name + "_" + fpga_data.model_id)
    # run symbiflow
    res = RunSymbiFlow.delay(PART_NAME=PART_NAME, PRJ_DIR=PRJ_DIR, PRJ_DIR_HOST=PRJ_DIR_HOST, TOP_FILE=TOP_FILE, mode=mode)
    return res.id

# FPGA entity
class FPGA(db.Model):
    __tablename__ = "FPGA"

    id = db.Column(db.Integer, primary_key=True)
    family = db.Column(db.String(20))
    model_id = db.Column(db.String(20), unique=False)
    builder = db.Column(db.String(20))

    def __init__(self, family, model_id, builder):
        self.family = family
        self.model_id = model_id
        self.builder = builder


# FPGA Schema
class FPGASchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = FPGA
        include_fk = True


# Project entity
class Project(db.Model):
    __tablename__ = "Project"

    id = db.Column(db.Integer, primary_key=True)
    Project_name = db.Column(db.String(20), unique=False)
    FPGA_id = db.Column(db.Integer, db.ForeignKey('FPGA.id'))

    def __init__(self, Project_name, FPGA_id):
        self.Project_name = Project_name
        self.FPGA_id = FPGA_id


# Project Schema
class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        include_fk = True


# HDL_file entity
class HDL_file(db.Model):
    __tablename__ = "HDL_file"

    id = db.Column(db.Integer, primary_key=True)
    Project_id = db.Column(db.Integer, db.ForeignKey('Project.id'), nullable=False)
    file_name = db.Column(db.String(20))
    top_level_flag = db.Column(db.Boolean, nullable=False)

    def __init__(self, Project_id, file_name, top_level_flag):
        self.Project_id = Project_id
        self.file_name = file_name
        self.top_level_flag = top_level_flag


# HDL_file Schema
class HDL_fileSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = HDL_file
        include_fk = True


# FPGA Table manager
class manage_fpga(Resource):
    # LIST FPGA
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            data = FPGA.query.all()
            if not data:
                return "Error: No FPGAs in table", 404
            data_schema = FPGASchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = FPGA.query.get(id)
            if not data:
                return "Error: The FPGA doesn't exist", 404
            data_schema = FPGASchema()
            return jsonify(data_schema.dump(data))

    # INSERT FPGA
    @staticmethod
    def post():
        family = request.json['family']
        model_id = request.json['model_id']
        builder = request.json['builder']

        # Check if it already exists
        check = FPGA.query.filter_by(family=family, model_id=model_id, builder=builder).first()
        if check:
            return "Error: FPGA already exists", 400

        # Create record
        data = FPGA(family, model_id, builder)
        try:
            db.session.add(data)
            db.session.commit()
        except Exception as e:
            print(e)
            return "Error: insertion aborted", 500
        else:
            return "Success: insertion done", 201

    # UPDATE FPGA
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for UPDATE", 400
        else:
            try:
                data = FPGA.query.get(id)

                # check for FPGA exixstance
                if data is None:
                    return "Error: The FPGA doesn't exist", 412

                family = request.json['family']
                model_id = request.json['model_id']
                builder = request.json['builder']

                # Check if it already exists
                check = FPGA.query.filter_by(family=family, model_id=model_id, builder=builder).first()
                if check:
                    return "Error: FPGA already exists", 400

                data.family = family
                data.model_id = model_id
                data.builder = builder

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted", 500
            else:
                return "Succes: update done", 200

    # DELETE FPGA
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for DELETE", 400
        else:
            try:
                fpga_data = FPGA.query.get(id)

                # check for FPGA exixstance
                if fpga_data is None:
                    return "Error: The FPGA doesn't exist", 412

                db.session.delete(fpga_data)
                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: deletion aborted", 500
            else:
                return "Success: deletion done", 200


# Project Table manager
class manage_project(Resource):
    # LIST Project
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            data = Project.query.all()
            if not data:
                return "Error: No Projects in table", 404
            data_schema = ProjectSchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = Project.query.get(id)
            if not data:
                return "Error: The Project doesn't exist", 404
            data_schema = ProjectSchema()
            return jsonify(data_schema.dump(data))

    # INSERT Project
    @staticmethod
    def post():
        Project_name = request.json['Project_name']
        FPGA_id = request.json['FPGA_id']

        # Check if already exists
        check = Project.query.filter_by(Project_name=Project_name, FPGA_id=FPGA_id).first()
        if check:
            return "Error: project already exists", 400

        # Creating the record
        data = Project(Project_name, FPGA_id)

        # finding folder name for proj
        Curr = os.getcwd()
        tmp = FPGA.query.get(FPGA_id)
        dir_name = os.path.join(Curr, Project_name + "_" + tmp.model_id)

        try:
            db.session.add(data)
            db.session.commit()
            os.mkdir(dir_name)
        except Exception as e:
            print(e)
            return "Error: insertion aborted", 500
        else:
            return "Success: insertion done", 201

    # UPDATE Project
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for UPDATE", 400
        else:
            try:
                data = Project.query.get(id)
                Project_name = request.json['Project_name']
                FPGA_id = request.json['FPGA_id']

                # Check if already exists
                check = Project.query.filter_by(Project_name=Project_name, FPGA_id=FPGA_id).first()
                if check:
                    return "Error: project already exists", 400

                # check if changes

                Curr = os.getcwd()
                # get old dir name
                tmp_src = FPGA.query.get(data.FPGA_id)
                dir_name_src = os.path.join(Curr, data.Project_name + "_" + tmp_src.model_id)
                # get new dir name
                tmp_dst = FPGA.query.get(FPGA_id)
                dir_name_dst = os.path.join(Curr, Project_name + "_" + tmp_dst.model_id)

                # update row
                data.Project_name = Project_name
                data.FPGA_id = FPGA_id
                # update dir
                os.rename(dir_name_src, dir_name_dst)

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted", 500
            else:
                return "Succes: update done", 200

    # DELETE project
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for DELETE", 400
        else:
            try:
                data = Project.query.get(id)

                # check if exists
                if data is None:
                    return "Error: project doesn't exists", 412

                # finding folder name for proj
                Curr = os.getcwd()
                tmp = FPGA.query.get(data.FPGA_id)
                dir_name = os.path.join(Curr, data.Project_name + "_" + tmp.model_id)

                # remove files attached to project
                RecursiveHDLDelete(id, dir_name)

                # remove the project
                db.session.delete(data)
                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: deletion aborted", 500
            else:
                return "Success: deletion done", 200


# HDL_file Table manager
class manage_HDL_file(Resource):
    #LIST HDL_file
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            data = HDL_file.query.all()
            if not data:
                return "Error: No HDL files in table", 404
            data_schema = HDL_fileSchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = HDL_file.query.get(id)
            if not data:
                return "Error: HDL file doesn't exist", 404
            data_schema = HDL_fileSchema()
            return jsonify(data_schema.dump(data))

    # INSERT HDL_file
    @staticmethod
    def post():
        # fetch data from request
        hdl = request.files.get('file')
        json_data = json.loads(request.form['json'])

        # fetch json data
        Project_id = json_data['Project_id']
        top_level_flag = json_data['top_level_flag']

        # check project existance
        project_data = Project.query.get(Project_id)
        if project_data is None:
            return "Error: The project doesn't exist", 412

        # check if HDL it exists
        check = HDL_file.query.filter_by(Project_id=Project_id, file_name=hdl.filename).first()
        if check:
            return "Error: HDL file already exists", 400

        # check if Top level entity is there
        if top_level_flag:
            check = HDL_file.query.filter_by(Project_id=Project_id, top_level_flag=True).first()
            if check:
                return "Error: Top level entity already exists", 400

        # finding folder name for proj
        Curr = os.getcwd()
        fpga_data = FPGA.query.get(project_data.FPGA_id)
        dir_name = os.path.join(Curr, project_data.Project_name + "_" + fpga_data.model_id + "/")

        # assemble record
        data = HDL_file(Project_id, hdl.filename, top_level_flag)
        try:
            hdl.save(dir_name + hdl.filename)
            db.session.add(data)
            db.session.commit()
        except Exception as e:
            print(e)
            return "Error: insertion aborted", 500
        else:
            return "Success: insertion done", 201

    # UPDATE HDL_file
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for UPDATE", 400
        else:
            try:
                data = HDL_file.query.get(id)

                # check if HDL file is on record
                if data is None:
                    return "Error: HDL file doesn't exist", 412

                # fetch data from request
                hdl = request.files.get('file')
                json_data = json.loads(request.form['json'])

                # fetch json data
                Project_id = json_data['Project_id']
                top_level_flag = json_data['top_level_flag']

                # get old file path
                Curr = os.getcwd()
                project_data_src = Project.query.get(data.Project_id)
                fpga_data_src = FPGA.query.get(project_data_src.FPGA_id)
                file_path_src = os.path.join(Curr, project_data_src.Project_name + "_" + fpga_data_src.model_id + "/" + data.file_name)
                # get new dir name
                project_data_dst = Project.query.get(Project_id)
                fpga_data_dst = FPGA.query.get(project_data_dst.FPGA_id)
                file_path_dst = os.path.join(Curr, project_data_dst.Project_name + "_" + fpga_data_dst.model_id + "/" + hdl.filename)

                # Update file name
                os.rename(file_path_src, file_path_dst)

                # update row
                data.Project_id = Project_id
                data.file_name = hdl.filename
                data.top_level_flag = top_level_flag

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted", 500
            else:
                return "Succes: update done", 200

    # DELETE HDL_file
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for DELETE", 400
        else:
            try:
                data = HDL_file.query.get(id)

                # check if HDL file is on record
                if data is None:
                    return "Error: HDL file doesn't exist", 412

                # finding file name for HDL
                Curr = os.getcwd()
                project_data = Project.query.get(data.Project_id)
                fpga_data = FPGA.query.get(project_data.FPGA_id)
                file_path = os.path.join(Curr, project_data.Project_name + "_" + fpga_data.model_id + "/" + data.file_name)

                os.remove(file_path)
                db.session.delete(data)
                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: deletion aborted", 500
            else:
                return "Success: deletion done", 200


# SymbiflowRunner
class run_toolchain(Resource):
    @staticmethod
    def get():
        try:
            process_id = request.args.get('id')
            task_result = RunSymbiFlow.AsyncResult(process_id)
            result = {
                'task_id': process_id,
                'task_status': task_result.status,
                'task_result': task_result.result
            }
            return make_response(jsonify(result), 200)
        except Exception as e:
            print(e)
            return "Error: no id for process status", 400

    @staticmethod
    def post():

        id = request.json['id']
        mode = request.json['mode']
        toolchain = request.json['toolchain']

        if not id:
            return "Error: No ID for Project", 400
        else:
            # check if mode is correct
            if (mode != 0 and mode != 1):
                print("No mode specified: Defaulting to 2")
                mode = 2
            data = Project.query.get(id)
            if not data:
                return "Error: The Project doesn't exist", 412

            if (toolchain == "symbiflow"):
                process_id = SymbiflowHelper(data, mode)
            else:
                return "Error: no toolchain selected", 400

            return process_id, 202


# Setting website resources
api.add_resource(manage_fpga, '/fpga')
api.add_resource(manage_project, '/project')
api.add_resource(manage_HDL_file, '/file')
api.add_resource(run_toolchain, '/toolchain')

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)
