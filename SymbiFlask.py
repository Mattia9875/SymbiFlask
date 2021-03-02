from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_restful import Resource, Api
from flask_marshmallow import Marshmallow
import os, json

app = Flask(__name__)
api = Api(app)
# Configuring the database path
app.config['SQLALCHEMY_DATABASE_URI']= 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# database object
db = SQLAlchemy(app)
# marshmallow object
ma = Marshmallow(app)

# function to recursively delete a project dir
def RecursiveHDLDelete(query_id, dir_name):
    try:
        #gather the file and record list
        dir_list = os.listdir(dir_name)
        db_list = HDL_file.query.filter_by(Project_id=query_id).all()
        #cycle files
        for file_name in dir_list:
            file_path = os.path.join(dir_name, file_name)
            os.remove(file_path)
        #cycle records
        for row in db_list:
            db.session.delete(row)
    except Exception as e:
        print(e)
        raise "Recursive delete failed"
        return
    else:
        return

# function to run bitstream generation
def RunSymbiFlow(prj_id):

    # gather data from the database
    prj_data = Project.query.get(prj_id)
    fpga_data = FPGA.query.get(prj_data.FPGA_id)
    top_level = HDL_file.query.filter_by(Project_id=prj_id, top_level_flag=True).first()
    # FPGA model
    PART_NAME = fpga_data.model_id
    # top level entity file
    TOP_FILE  = top_level.file_name
    # container project folder
    PRJ_DIR   = os.path.join("/symb", prj_data.Project_name + "_" + fpga_data.model_id)
    # host project folder
    PRJ_DIR_HOST   = os.path.join( os.getcwd() , prj_data.Project_name + "_" + fpga_data.model_id)
    # create the docker cmd
    cmd = ("docker run --rm -it"
        " -e PART_NAME=" + PART_NAME + " -e TOP_FILE=" + TOP_FILE + " -e PRJ_DIR=" + PRJ_DIR +
        " --privileged -v /dev/bus/usb:/dev/bus/usb" + " -v " + PRJ_DIR_HOST + ":" + PRJ_DIR +
        " symbiflow:latest")
    
    # debug print
    print(cmd)
    try:
        # execute the cmd
        os.system(cmd)
    except Exception as e:
        print(e)
        return True
    else:
        return False

#FPGA entity
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

#FPGA Schema
class FPGASchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = FPGA
        include_fk = True

#Project entity
class Project(db.Model):
    __tablename__ = "Project"

    id = db.Column(db.Integer, primary_key=True)
    Project_name = db.Column(db.String(20), unique=False)
    FPGA_id = db.Column(db.Integer, db.ForeignKey('FPGA.id'))

    def __init__(self, Project_name, FPGA_id):
        self.Project_name = Project_name
        self.FPGA_id = FPGA_id

#Project Schema
class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        include_fk = True

#HDL_file entity
class HDL_file(db.Model):
    __tablename__ = "HDL_file"

    id = db.Column(db.Integer, primary_key=True)
    Project_id = db.Column(db.Integer, db.ForeignKey('Project.id'), nullable=False)
    file_name = db.Column(db.String(20))
    top_level_flag = db.Column(db.Boolean, nullable=False)

    def __init__(self, Project_id ,file_name, top_level_flag):
        self.Project_id = Project_id
        self.file_name = file_name
        self.top_level_flag = top_level_flag

#HDL_file Schema
class HDL_fileSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = HDL_file
        include_fk = True

#FPGA Table manager
class manage_fpga(Resource):
    #LIST FPGA
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            data = FPGA.query.all()
            if not data:
                    return "Error: No FPGAs in table"
            data_schema = FPGASchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = FPGA.query.get(id)
            if not data:
                    return "Error: The FPGA doesn't exist"
            data_schema = FPGASchema()
            return jsonify(data_schema.dump(data))

    #INSERT FPGA
    @staticmethod
    def post():
        family = request.json['family']
        model_id = request.json['model_id']
        builder = request.json['builder']

        #Check if it already exists
        check = FPGA.query.filter_by(family=family, model_id=model_id, builder=builder).first()
        if check:
            return "Error: FPGA already exists"

        #Create record
        data = FPGA(family, model_id, builder)
        try:
            db.session.add(data)
            db.session.commit()
        except Exception as e:
            print(e)
            return "Error: insertion aborted"
        else:
            return "Success: insertion done"

    #UPDATE FPGA
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as _:
            id = None

        if not id:
            return "Error: No ID for UPDATE"
        else:
            try:
                data = FPGA.query.get(id)

                #check for FPGA exixstance
                if (data==None):
                    return "Error: The FPGA doesn't exist"

                family = request.json['family']
                model_id = request.json['model_id']
                builder = request.json['builder']

                #Check if it already exists
                check = FPGA.query.filter_by(family=family, model_id=model_id, builder=builder).first()
                if check:
                    return "Error: FPGA already exists"
                
                data.family = family
                data.model_id = model_id
                data.builder = builder

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted"
            else:
                return "Succes: update done"

    #DELETE FPGA
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as _:
            id = None
        
        if not id:
            return "Error: No ID for DELETE"
        else:
            try:
                fpga_data = FPGA.query.get(id)
                
                #check for FPGA exixstance
                if (fpga_data==None):
                    return "Error: The FPGA doesn't exist"

                db.session.delete(fpga_data)
                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: deletion aborted"
            else:
                return "Success: deletion done"

#Project Table manager
class manage_project(Resource):
    #LIST Project
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            data = Project.query.all()
            if not data:
                    return "Error: No Projects in table"
            data_schema = ProjectSchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = Project.query.get(id)
            if not data:
                    return "Error: The Project doesn't exist"
            data_schema = ProjectSchema()
            return jsonify(data_schema.dump(data))

    #INSERT Project
    @staticmethod
    def post():
        Project_name = request.json['Project_name']
        FPGA_id = request.json['FPGA_id']

        #Check if already exists
        check = Project.query.filter_by(Project_name=Project_name, FPGA_id=FPGA_id).first()
        if check :
            return "Error: project already exists"

        #Creating the record
        data = Project(Project_name,FPGA_id)
        
        #finding folder name for proj
        Curr = os.getcwd()
        tmp = FPGA.query.get(FPGA_id)
        dir_name = os.path.join(Curr, Project_name + "_" + tmp.model_id)

        try:
            db.session.add(data)
            db.session.commit()
            os.mkdir(dir_name)
        except Exception as e:
            print(e)
            return "Error: insertion aborted"
        else:
            return "Success: insertion done"

    #UPDATE Project
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as _:
            id = None

        if not id:
            return "Error: No ID for UPDATE"
        else:
            try:
                data = Project.query.get(id)
                Project_name = request.json['Project_name']
                FPGA_id = request.json['FPGA_id']

                #Check if already exists
                check = Project.query.filter_by(Project_name=Project_name, FPGA_id=FPGA_id).first()
                if check :
                    return "Error: project already exists"

                #check if changes

                Curr = os.getcwd()
                #get old dir name
                tmp_src = FPGA.query.get(data.FPGA_id)
                dir_name_src = os.path.join(Curr, data.Project_name + "_" + tmp_src.model_id)
                #get new dir name
                tmp_dst = FPGA.query.get(FPGA_id)
                dir_name_dst = os.path.join(Curr, Project_name + "_" + tmp_dst.model_id)

                #update row
                data.Project_name = Project_name
                data.FPGA_id = FPGA_id
                #update dir
                os.rename(dir_name_src, dir_name_dst)

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted"
            else:
                return "Succes: update done"

    #DELETE project
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as _:
            id = None
        
        if not id:
            return "Error: No ID for DELETE"
        else:
            try:
                data = Project.query.get(id)

                #check if exists
                if (data==None):
                    return "Error: project doesn't exists"

                #finding folder name for proj
                Curr = os.getcwd()
                tmp = FPGA.query.get(data.FPGA_id)
                dir_name = os.path.join(Curr, data.Project_name + "_" + tmp.model_id)

                #remove files attached to project
                RecursiveHDLDelete(id, dir_name)

                #remove the project
                db.session.delete(data)
                db.session.commit()
                os.rmdir(dir_name)
            except Exception as e:
                print(e)
                return "Error: deletion aborted"
            else:
                return "Success: deletion done"

#HDL_file Table manager
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
                    return "Error: No HDL files in table"
            data_schema = HDL_fileSchema(many=True)
            return jsonify(data_schema.dump(data))
        else:
            data = HDL_file.query.get(id)
            if not data:
                    return "Error: HDL file doesn't exist"
            data_schema = HDL_fileSchema()
            return jsonify(data_schema.dump(data))

    #INSERT HDL_file
    @staticmethod
    def post():
        """
        print("\n\n")
        print (request.files.get('file'))
        print (type(request.files.get('file')))

        print (request.form.getlist('json'))
        print (type(request.form.getlist('json')[0]))
        print("\n\n")
        """
        #fetch file from request
        hdl = request.files.get('file')

        #fetch json data
        db_data = json.loads(request.form.getlist('json')[0])
        Project_id = db_data["Project_id"]
        top_level_flag = db_data["top_level_flag"]

        #check project existance
        project_data = Project.query.get(Project_id)
        if (project_data==None):
            return "Error: The project doesn't exist"

        #check if HDL it exists
        check = HDL_file.query.filter_by(Project_id=Project_id, file_name=hdl.filename).first()
        if check:
            return "Error: HDL file already exists"

        #check if Top level entity is there
        if (top_level_flag == True):
            check = HDL_file.query.filter_by(Project_id=Project_id, top_level_flag=True).first()
            if check:
                return "Error: Top level entity already exists"

        #finding folder name for proj
        Curr = os.getcwd()
        fpga_data = FPGA.query.get(project_data.FPGA_id)
        dir_name = os.path.join(Curr, project_data.Project_name + "_" + fpga_data.model_id + "/")

        #assemble record
        data = HDL_file(Project_id, hdl.filename, top_level_flag)
        try:    
            hdl.save(dir_name + hdl.filename)
            db.session.add(data)
            db.session.commit()
        except Exception as e:
            print(e)
            return "Error: insertion aborted"
        else:
            return "Success: insertion done"

    #UPDATE HDL_file
    @staticmethod
    def put():
        try:
            id = request.args['id']
        except Exception as _:
            id = None

        if not id:
            return "Error: No ID for UPDATE"
        else:
            try:
                data = HDL_file.query.get(id)

                #check if HDL file is on record
                if (data==None):
                    return "Error: HDL file doesn't exist"

                #fetch file from request
                hdl = request.files.get('file')

                #fetch json data
                db_data = json.loads(request.form.getlist('json')[0])
                Project_id = db_data["Project_id"]
                top_level_flag = db_data["top_level_flag"]

                #get old file path
                Curr = os.getcwd()
                project_data_src = Project.query.get(data.Project_id)
                fpga_data_src = FPGA.query.get(project_data_src.FPGA_id)
                file_path_src = os.path.join(Curr, project_data_src.Project_name + "_" + fpga_data_src.model_id + "/" + data.file_name)
                #get new dir name
                project_data_dst = Project.query.get(Project_id)
                fpga_data_dst = FPGA.query.get(project_data_dst.FPGA_id)
                file_path_dst = os.path.join(Curr, project_data_dst.Project_name + "_" + fpga_data_dst.model_id + "/" + hdl.filename)

                #Update file name
                os.rename(file_path_src, file_path_dst)

                #update row
                data.Project_id = Project_id
                data.file_name = hdl.filename
                data.top_level_flag = top_level_flag

                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: update aborted"
            else:
                return "Succes: update done"

    #DELETE HDL_file
    @staticmethod
    def delete():
        try:
            id = request.args['id']
        except Exception as _:
            id = None
        
        if not id:
            return "Error: No ID for DELETE"
        else:
            try:
                data = HDL_file.query.get(id)

                #check if HDL file is on record
                if (data==None):
                    return "Error: HDL file doesn't exist"

                #finding file name for HDL
                Curr = os.getcwd()
                project_data = Project.query.get(data.Project_id)
                fpga_data = FPGA.query.get(project_data.FPGA_id)
                file_path = os.path.join(Curr, project_data.Project_name + "_" + fpga_data.model_id + "/" + data.file_name)

                os.remove(file_path)
                db.session.delete(data)
                db.session.commit()
            except Exception as e:
                print(e)
                return "Error: deletion aborted"
            else:
                return "Success: deletion done"

#SymbiflowRunner

class run_symbiflow(Resource):
    @staticmethod
    def get():
        try:
            id = request.args['id']
        except Exception as e:
            id = None

        if not id:
            return "Error: No ID for Project"
        else:
            data = Project.query.get(id)
            if not data:
                return "Error: The Project doesn't exist"
            check = RunSymbiFlow(id)
            if (check == True):
                return "Error: Somithing went wrong during configuration"
            else:
                return "Success: Design compiled without problems"



#Setting website resources
api.add_resource(manage_fpga, '/fpga')
api.add_resource(manage_project, '/project')
api.add_resource(manage_HDL_file, '/file')
api.add_resource(run_symbiflow, '/symbiflow')

if __name__ == '__main__':
    app.run(debug=True)


