#TODO 
Following is the art installation that I am working on: https://www.instructables.com/Reflective-Resonance/
My objective with this project directory for the art exhibition is to: 
- Build a UI with 6 slots where each slot is representative of the speaker in the installation, and the user can choose to load an agent in one of the six slots, which means that any text response from that agent will be converted into the parameters for the speaker to control the wave that is being created to match with the text response of the agent. So basically the 6 speakers can be mapped to 6 different agents or the same agents, any combination of agents would work. 
- Build a multi-agent system (using rawagents package) [I will provide info on how to use this package later]. Based on the agents that are loaded we will feed the message of the user into the 6 different agents and then wait for them to respond and then their text responses will be converted to the parameters for the speaker (the conversion is something we don't have to worry about at the moment, it will come later as another team member is working on it)

So at the moment, what we need to build is: 
- A simple and minimalist UI that is artistic looking that has a simple list of already precreated agents on the left and on the right there are six circles (which represent the 6 speakers in the installation), the user can drag and drop agents in the circle to load them in the respective location. 
- For now we will have the system run on text and not on voice, so we should have a text box appear at the bottom of the UI once all the 6 agents that we want to get responses from are loaded in, the user can type a message in the text box and send it to the agent and see all the 6 agent responses as they come in. 
- In the beginning we can allow the user to select from a list of 6 agents, so they can choose to have each agent be loaded in one of the speakers or they can load the same agent in multiple speaker. In the MVP version, we won't be building the personalities for the agent, all of the agents are going to be simple chat agents with the `model` parameter varying but the system prompt that is used by all the agents is going to be same (for now, later we will introduce personalities). So basically each agent is going to be a different llm model and we can start with the following six: 
1. Claude Sonnit 4.5
2. Claude Opus 4.5 
3. GPT 5.2 
4. GPT 5.1 
5. GPT 4o
6. Gemini 3

The overall flow of the system is going to be (we aren't building this but the MVP version of it mentioned below):
User Audio --> STT --> Send Message to Agents --> Wait for Agent Response --> Use ML to convert Agent response to speaker parameters --> Send the speaker parameters as events to touch designer --> User sees the water respond to its conversation 

#### The MVP Version we are trying to build: 
- The MVP verison is going to be based on text instead of audio, to build the core functionality and test it easily and then we will add the audio part later. This way we can ensure the agent setup and the UI is build properly and then add the other required features. 

#### Next Work
One thing that is still an open question that we will need to figure out after the MVP is build, is at the moment in the initial version we only have the user talking to the 6 agents, can we make it such that the agents also converse among each other to help the user. So the agents not only respond to the user build also respond to each other to generate the final output, but this will be more clear once we have build the initial version. 