# start by pulling the python image
FROM python:3.12

# switch working directory
WORKDIR /app
# copy every content from the local file to the image
COPY . .

# install the dependencies and packages in the requirements file
RUN pip3 install -r requirements.txt

# configure the container to run in an executed manner
ENTRYPOINT [ "python3" ]
CMD ["main.py" ]
