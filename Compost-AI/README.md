## Summary
Compost AI is an AI-Powered Smart Bin designed to reduce food waste in school cafeterias. It is a component of **SchoolPrint**, which is a suite of edge AI toolds design to help reduce a school's environmental footprint. This directory contains the dataset, code, results and model weights of the Compost AI waste classification model. Compost AI used transfer learning from ImageNet weights and was built on an *EfficientNet-B0* backbone. 

## Problem
***[One-third of all food in the United States goes uneaten](https://www.epa.gov/recycle/preventing-wasted-food-home)*** and ends up in our municipal solid waste stream. Fortunately, composting can solve this. Composting is a process of naturally recycling food scraps so that they can be used to create more nutrient rich soil. However, ***[96% of wasted food ended up in landfills](https://www.epa.gov/recycle/preventing-wasted-food-home)*** instead of being composted. This is for 2 reasons:

1. First, food scraps that are sent to composting are often mixed with non-compostable items like plastic and glass, so they are bundled together and sent to the landfill instead because [contamination facilities automatically reject any load of food waste that’s contaminated](https://www.wastedive.com/news/biocycle-2023-composting-survey-closed-loop/689945/)

2. Second, many schools [don’t have a compost bin](https://modernfarmer.com/2024/03/composting-makes-sense-why-dont-more-cities-do-it/) in their homes (This includes public places like airports, parks, supermarkets, etc. too)

## Solution
An AI smart bin that uses computer vision can re-route food waste from landfills to composting if it’s deployed at a massive scale. The “bin” will come with three bins inside of it: `garbage`, `recycling` and `compost`. The bin will also be connected to an app, which will have a dashboard that shows which items were sorted into which bin (human-in-the-loop to verify if AI output is correct) and will also send alerts to the school to let them know when a bin is full and they have to take it out.  

- **Software:** A CNN that can take an image of the waste items as input and determine if it belongs in either the garbage, recycling and compost.

- **Hardware:** A Raspberry Pi 4 to run model inference + camera module capture images of the inputted waste item + a container with three bins to hold sorted waste +ultrasonic sensor to detect when bin is full + 3 servo motors.


## Training Dataset
The [Recyclable and Household Waste Classification Dataset](https://www.kaggle.com/datasets/alistairking/recyclable-and-household-waste-classification) on Kaggle was used to train the Compost AI model. This dataset was chosen for 2 reasons:

1. It's a comprehensive dataset with over **15,000 images** across **30 classes** that covers wide range of categories including: `Plastic`, `Paper`, `Cardboard`, `Glass`, `Metal`, `Organic Waste` and `Textiles`.

2. The dataset offers 500 images per class, which is further split into 2 directories. The `default` folder offers a studio-image like representation of the waste item and the `real_world`folder offers images of the waste item in a real-world scenario. 

## Results
Compost AI achieved a ***96.36 percent*** accuracy on disposal pathway adjusted accuracy. That means when given any input image of a waste item, it was able to correctly categorize the item into either garbage, recycling or compost ~96% of the time. In contrast, when Compost AI was evaluated on categorizing an input image of a waste item into one of the 30 classes of waste in the dataset, it only achieved an ***87.60 percent*** accuracy. 

Becuase there is more granularity among the classes, Compost AI initially had a lower accuracy rate; however, becuase our smart bin is only concerned with sorting waste items into one of the three disposal pathways and not determining what type of object the waste item is we can safely take the results of the disposal pathway adjusted accuracy which is ~96%. After quantizing the model files into a `.tflite` format so that it could run inference on a Raspberry Pi 4, the accuracy dropped to ***~92 percent***. 

<br>

<img src="https://github.com/user-attachments/assets/fec5e73a-1013-429b-b031-929597327ca6" width="49%" /> 
<img src="https://github.com/user-attachments/assets/91591bbb-5235-4af4-994a-cd77354fe237" width="49%" />