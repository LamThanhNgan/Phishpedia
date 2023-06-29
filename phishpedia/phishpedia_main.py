from .phishpedia_config import *
import os
import argparse
import time
from .src.util.chrome import *
# import os
os.environ["KMP_DUPLICATE_LIB_OK"]="TRUE"

#####################################################################################################################
# ** Step 1: Enter Layout detector, get predicted elements
# ** Step 2: Enter Siamese, siamese match a phishing target, get phishing target

# **         If Siamese report no target, Return Benign, None
# **         Else Siamese report a target, Return Phish, phishing target
#####################################################################################################################


def phishpedia_prediction(url, screenshot_path, ELE_MODEL, SIAMESE_THRE, SIAMESE_MODEL, LOGO_FEATS, LOGO_FILES, DOMAIN_MAP_PATH):
    '''
    Phishdiscovery for phishpedia main script
    :param url: URL
    :param screenshot_path: path to screenshot
    :param ELE_MODEL: logo detector
    :param SIAMESE_THRE: threshold for Siamese
    :param SIAMESE_MODEL: siamese model
    :param LOGO_FEATS: cached reference logo features
    :param LOGO_FILES: cached reference logo paths
    :param DOMAIN_MAP_PATH: domain map.pkl
    :return phish_category: 0 for benign 1 for phish
    :return pred_target: None or phishing target
    :return plotvis: predicted image
    :return siamese_conf: siamese matching confidence
    '''
    # 0 for benign, 1 for phish, default is benign
    phish_category = 0
    pred_target = None
    siamese_conf = None
    print("Entering phishpedia")

    ####################### Step1: layout detector ##############################################
    # logo_boxes, logo_scores, input_boxes, input_scores
    pred_boxes, logo_scores, input_boxes, input_scores = pred_rcnn(im=screenshot_path, predictor=ELE_MODEL)
    print("======================RCNN=====================")
    print("Logo: ", pred_boxes)
    print("Logo score: ", logo_scores)
    print("Input boxes: ", input_boxes)
    print("Input score: ", input_scores)


    if pred_boxes is not None:
        pred_boxes = pred_boxes.detach().cpu().numpy()
        input_boxes = input_boxes.detach().cpu().numpy()

    plotvis = vis(screenshot_path, pred_boxes)
    
    print("plot")
    # If no element is reported
    if pred_boxes is None or len(pred_boxes) == 0:
        print('No element is detected, report as benign')
        return phish_category, pred_target, plotvis, siamese_conf, pred_boxes
    
    print('Entering siamese')


    ######################## Step2: Siamese (logo matcher) ########################################
    pred_target, matched_coord, siamese_conf, isBegninDomains = phishpedia_classifier_logo(logo_boxes=pred_boxes,
                                                                     domain_map_path=DOMAIN_MAP_PATH,
                                                                     model=SIAMESE_MODEL,
                                                                     logo_feat_list=LOGO_FEATS,
                                                                     file_name_list=LOGO_FILES,
                                                                     url=url,
                                                                     shot_path=screenshot_path,
                                                                     ts=SIAMESE_THRE)

    if pred_target is None:
        print('Did not match to any brand, report as benign')
        return phish_category, pred_target, plotvis, input_boxes,siamese_conf, pred_boxes
    elif isBegninDomains == True:
        phish_category = 0
        cv2.putText(plotvis, "Target has been identified as normal: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                    (int(matched_coord[0] - 20), int(matched_coord[1] + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
        return phish_category, pred_target, plotvis, input_boxes, siamese_conf, pred_boxes
    else:
        
        phish_category = 1
        # Visualize, add annotations
        cv2.putText(plotvis, "Target has been identified as phishing: {} with confidence {:.4f}".format(pred_target, siamese_conf),
                    (int(matched_coord[0] - 20), int(matched_coord[1] + 20)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    return phish_category, pred_target, plotvis,input_boxes ,siamese_conf, pred_boxes


def runit(full_path,  ELE_MODEL, SIAMESE_THRE, SIAMESE_MODEL, LOGO_FEATS, LOGO_FILES, DOMAIN_MAP_PATH):
    # results_path = results

    # if not os.path.exists(results_path):
    #     with open(results_path, "w+") as f:
    #         f.write("folder" + "\t")
    #         f.write("url" + "\t")
    #         f.write("phish" + "\t")
    #         f.write("prediction" + "\t")  # write top1 prediction only
    #         f.write("siamese_conf" + "\t")
    #         f.write("vt_result" + "\t")
    #         f.write("runtime" + "\n")

    
    start_time = time.time()

    screenshot_path = os.path.join(full_path, "shot.png")
    info_path = os.path.join(full_path, 'info.txt')

    
    url = open(info_path, encoding='ISO-8859-1').read()
    

    phish_category, phish_target, plotvis,input_boxes, siamese_conf, pred_boxes = phishpedia_prediction(url=url, screenshot_path=screenshot_path,
                                                                            ELE_MODEL=ELE_MODEL,
                                                                            SIAMESE_THRE=SIAMESE_THRE,
                                                                            SIAMESE_MODEL=SIAMESE_MODEL,
                                                                            LOGO_FEATS=LOGO_FEATS,
                                                                            LOGO_FILES=LOGO_FILES,
                                                                            DOMAIN_MAP_PATH=DOMAIN_MAP_PATH)
    # print('Phishing (1) or Benign (0) ?', phish_category)
    # print('What is its targeted brand if it is a phishing ?', phish_target)
    # print('What is the siamese matching confidence ?', siamese_conf)
    # print('Where is the predicted logo (in [x_min, y_min, x_max, y_max])?', pred_boxes)

    # FIXME: call VTScan only when phishpedia report it as phishing
    vt_result = "None"
    if phish_target is not None:
        try:
            if vt_scan(url) is not None:
                positive, total, scans_result = vt_scan(url)
                print("Positive VT scan!")
                vt_result = str(positive) + "/" + str(total) + "-" + scans_result 
                print(vt_result)
            else:
                print("Negative VT scan!")
                vt_result = "None"

        except Exception as e:
            print('VTScan is not working...')
            print(e)
            vt_result = "error"
    img_path = os.path.join(full_path, "predict.png")
    if plotvis is not None:
        cv2.imwrite(img_path, plotvis)
        co = inputBox(input_boxes)
        plotvis_input =  vis(img_path, input_boxes)

        if plotvis_input is not None and co is not None:
            # print("input_scores --------> ", input_scores)
            cv2.putText(plotvis_input, "Detect input boxes to enter your information.",
                    (int(co[0] + 50), int(co[1] + 80)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (11, 77, 218), 2)
            cv2.imwrite(img_path, plotvis_input)
    
    return phish_category, phish_target, siamese_conf, vt_result, img_path
    # write results as well as predicted images
    # try:
    #     with open(results_path, "a+", encoding='ISO-8859-1') as f:
    #         f.write(full_path + "\t")
    #         f.write(url + "\t")
    #         f.write(str(phish_category) + "\t")
    #         f.write(str(phish_target) + "\t")  # write top1 prediction only
    #         f.write(str(siamese_conf) + "\t")
    #         f.write(vt_result + "\t")
    #         f.write(str(round(time.time() - start_time, 4)) + "\n")

    #         if plotvis is not None:
    #             cv2.imwrite(os.path.join(full_path, "predict.png"), plotvis)
    # except UnicodeEncodeError:
    #     return


if __name__ == "__main__":

    # os.environ["CUDA_VISIBLE_DEVICES"]="1"
    parser = argparse.ArgumentParser()
    parser.add_argument('-f', "--folder", help='Input folder path to parse',  default='./datasets/cannot_detect_logo')
    parser.add_argument('-r', "--results", help='Input results file name', default='./debug.txt')
    parser.add_argument('-c', "--config", help='Config file path', default=None)
    args = parser.parse_args()
    date = args.folder.split('/')[-1]
    directory = args.folder
    results_path = args.results.split('.txt')[0] + "_pedia.txt"

    # ELE_MODEL, SIAMESE_THRE, SIAMESE_MODEL, LOGO_FEATS, LOGO_FILES, DOMAIN_MAP_PATH = load_config(args.config)
    #
    # if not os.path.exists(results_path):
    #     with open(results_path, "w+") as f:
    #         f.write("folder" + "\t")
    #         f.write("url" + "\t")
    #         f.write("phish" + "\t")
    #         f.write("prediction" + "\t")  # write top1 prediction only
    #         f.write("siamese_conf" + "\t")
    #         f.write("vt_result" + "\t")
    #         f.write("runtime" + "\n")
    #
    # for item in tqdm(os.listdir(directory)):
    #     start_time = time.time()
    #
    #     # if item in open(results_path, encoding='ISO-8859-1').read(): # have been predicted
    #     #     continue
    #
    #     try:
    #         print(item)
    #         full_path = os.path.join(directory, item)
    #
    #         screenshot_path = os.path.join(full_path, "shot.png")
    #         url = open(os.path.join(full_path, 'info.txt'), encoding='ISO-8859-1').read()
    #
    #         if not os.path.exists(screenshot_path):
    #             continue
    #
    #         else:
    #             phish_category, phish_target, plotvis, siamese_conf, pred_boxes = test(url=url, screenshot_path=screenshot_path,
    #                                                                                    ELE_MODEL=ELE_MODEL,
    #                                                                                    SIAMESE_THRE=SIAMESE_THRE,
    #                                                                                    SIAMESE_MODEL=SIAMESE_MODEL,
    #                                                                                    LOGO_FEATS=LOGO_FEATS,
    #                                                                                    LOGO_FILES=LOGO_FILES,
    #                                                                                    DOMAIN_MAP_PATH=DOMAIN_MAP_PATH)
    #
    #             # FIXME: call VTScan only when phishpedia report it as phishing
    #             vt_result = "None"
    #             if phish_target is not None:
    #                 try:
    #                     if vt_scan(url) is not None:
    #                         positive, total = vt_scan(url)
    #                         print("Positive VT scan!")
    #                         vt_result = str(positive) + "/" + str(total)
    #                     else:
    #                         print("Negative VT scan!")
    #                         vt_result = "None"
    #
    #                 except Exception as e:
    #                     print('VTScan is not working...')
    #                     vt_result = "error"
    #
    #             # write results as well as predicted images
    #             with open(results_path, "a+", encoding='ISO-8859-1') as f:
    #                 f.write(item + "\t")
    #                 f.write(url + "\t")
    #                 f.write(str(phish_category) + "\t")
    #                 f.write(str(phish_target) + "\t")  # write top1 prediction only
    #                 f.write(str(siamese_conf) + "\t")
    #                 f.write(vt_result + "\t")
    #                 f.write(str(round(time.time() - start_time, 4)) + "\n")
    #
    #             cv2.imwrite(os.path.join(full_path, "predict.png"), plotvis)
    #
    #     except Exception as e:
    #         print(str(e))
    #
    # #  raise(e)
    # time.sleep(2)



