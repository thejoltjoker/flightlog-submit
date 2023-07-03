# Flightlog Submit

> Docker container for automatically uploading tracklogs to Flightlog

Flightlog Submit is a Docker container that automates the process of uploading tracklogs to Flightlog. This repository
provides all the necessary files and configurations to get you up and running quickly.

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [License](#license)

## Features

- Easy and automated uploading of tracklogs to FlightLog.
- Dockerized solution for seamless deployment.
- Customizable configuration to suit your specific needs.
- Lightweight and efficient.

## Installation

To use Flightlog Submit, follow these steps:

1. Ensure that you have Docker installed on your system.
2. Clone this repository: `git clone https://github.com/thejoltjoker/flightlog-submit.git`
3. Navigate to the cloned directory: `cd flightlog-submit`
4. Build the Docker image: `docker build -t flightlog-submit .`

## Usage

Once you have completed the installation steps, you can run Flightlog Submit using the following command:

```bash
docker run --name flightlog-submit -v /path/to/tracklogs:/log flightlog-submit
```

Make sure to replace `/path/to/tracklogs` with the actual path to your tracklogs directory. 
The script checks for `year` subfolders so put all your tracklogs for 2023 in a subfolder called `2023` and so on.

## Configuration

Flightlog Submit can be configured using environment variables. The available configuration options are:

- `TRACKLOG_PATH`: Docker mount path (default: `/log`).
- `FLIGHTLOG_USERNAME`: Your FlightLog username.
- `FLIGHTLOG_PASSWORD`: Your FlightLog password.
- `USER_ID`: User id.
- `BRANDMODEL_ID`: Wing id.


You can set these environment variables either in a `.env` file or directly in the Docker run command.
## FAQ
### How do I find my brandmodel id?
Use the web inspector to find the id when you're on the _New flight_ page.
![Brandmodel ID example](https://i.imgur.com/ki6IvB6.png "Brandmodel ID example")

## License

Flightlog Submit is licensed under
the [MIT License](https://github.com/thejoltjoker/flightlog-submit/blob/main/LICENSE). Feel free to modify and
distribute this project as per the license terms.