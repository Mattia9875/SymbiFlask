from celery import Celery
import os
# celery instance
app = Celery('celerytask', backend='redis://localhost:6379', broker='redis://localhost:6379/0')

# delclaring the symbiflow runner script
@app.task
def RunSymbiFlow(PART_NAME, PRJ_DIR, PRJ_DIR_HOST, TOP_FILE, mode=2):

    # assemple the docker cmd
    cmd = ("docker run --rm -it"
           " -e BOARD_MODEL=" + PART_NAME + " -e TOP_FILE=" + TOP_FILE + " -e PRJ_DIR=" + PRJ_DIR +
           " -e MODE=" + str(mode) +
           " --privileged -v /dev/bus/usb:/dev/bus/usb" + " -v " + PRJ_DIR_HOST + ":" + PRJ_DIR +
           " symbiflow:" + PART_NAME)

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
